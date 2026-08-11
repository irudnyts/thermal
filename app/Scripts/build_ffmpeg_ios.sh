#!/bin/bash

set -euo pipefail

ffmpeg_version="8.1.2"
minimum_ios_version="17.0"
script_directory="$(cd "$(dirname "$0")" && pwd)"
app_directory="$(cd "$script_directory/.." && pwd)"
vendor_directory="$app_directory/Vendor/FFmpeg"
work_directory="$vendor_directory/.build"
source_archive="$work_directory/ffmpeg-$ffmpeg_version.tar.xz"
source_directory="$work_directory/ffmpeg-$ffmpeg_version"
xcframework_path="$vendor_directory/FFmpeg.xcframework"
download_url="https://ffmpeg.org/releases/ffmpeg-$ffmpeg_version.tar.xz"

if [[ ! -f "$app_directory/Stream.xcodeproj/project.pbxproj" ]]; then
    echo "error: run the checked-in script from the Stream app repository" >&2
    exit 1
fi

for required_command in curl make tar xcodebuild xcrun; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        echo "error: required command '$required_command' was not found" >&2
        exit 1
    fi
done

job_count="$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"

build_slice() {
    local sdk="$1"
    local target_triple="$2"
    local slice_name="$3"
    local sdk_path
    local clang_path
    local build_directory="$work_directory/build/$slice_name"
    local install_directory="$work_directory/install/$slice_name"
    local slice_directory="$work_directory/slices/$slice_name"

    sdk_path="$(xcrun --sdk "$sdk" --show-sdk-path)"
    clang_path="$(xcrun --sdk "$sdk" --find clang)"

    mkdir -p "$build_directory" "$install_directory" "$slice_directory/Headers"

    echo "Building FFmpeg $ffmpeg_version for $slice_name"
    cd "$build_directory"

    "$source_directory/configure" \
        --prefix="$install_directory" \
        --target-os=darwin \
        --arch=arm64 \
        --cc="$clang_path" \
        --sysroot="$sdk_path" \
        --enable-cross-compile \
        --enable-static \
        --disable-shared \
        --enable-pic \
        --disable-programs \
        --disable-doc \
        --disable-debug \
        --disable-autodetect \
        --disable-everything \
        --disable-gpl \
        --disable-version3 \
        --disable-nonfree \
        --disable-avdevice \
        --disable-avfilter \
        --disable-swresample \
        --disable-encoders \
        --disable-muxers \
        --disable-filters \
        --disable-indevs \
        --disable-outdevs \
        --disable-bsfs \
        --disable-videotoolbox \
        --disable-audiotoolbox \
        --enable-avcodec \
        --enable-avformat \
        --enable-avutil \
        --enable-swscale \
        --enable-network \
        --enable-pthreads \
        --enable-decoder=h264 \
        --enable-parser=h264 \
        --enable-demuxer=mpegts \
        --enable-protocol=udp \
        --enable-protocol=file \
        --extra-cflags="-target $target_triple -isysroot $sdk_path" \
        --extra-ldflags="-target $target_triple -isysroot $sdk_path"

    make -j "$job_count"
    make install

    xcrun --sdk "$sdk" libtool -static \
        -o "$slice_directory/libFFmpeg.a" \
        "$install_directory/lib/libavcodec.a" \
        "$install_directory/lib/libavformat.a" \
        "$install_directory/lib/libavutil.a" \
        "$install_directory/lib/libswscale.a"

    cp -R "$install_directory/include/." "$slice_directory/Headers/"
    printf '%s\n' \
        '#include <libavcodec/avcodec.h>' \
        '#include <libavformat/avformat.h>' \
        '#include <libavutil/avutil.h>' \
        '#include <libavutil/error.h>' \
        '#include <libavutil/frame.h>' \
        '#include <libavutil/time.h>' \
        '#include <libswscale/swscale.h>' \
        > "$slice_directory/Headers/FFmpeg.h"
    printf '%s\n' \
        'module FFmpeg [system] {' \
        '    umbrella header "FFmpeg.h"' \
        '    export *' \
        '}' > "$slice_directory/Headers/module.modulemap"
}

mkdir -p "$vendor_directory"
rm -rf "$work_directory" "$xcframework_path"
mkdir -p "$work_directory"

echo "Downloading official FFmpeg $ffmpeg_version source"
curl --fail --location --retry 3 --output "$source_archive" "$download_url"
tar -xJf "$source_archive" -C "$work_directory"

if [[ "$(tr -d '\r\n' < "$source_directory/RELEASE")" != "$ffmpeg_version" ]]; then
    echo "error: downloaded source does not report FFmpeg $ffmpeg_version" >&2
    exit 1
fi

build_slice iphoneos "arm64-apple-ios$minimum_ios_version" ios-arm64
build_slice iphonesimulator "arm64-apple-ios$minimum_ios_version-simulator" ios-arm64-simulator

xcodebuild -create-xcframework \
    -library "$work_directory/slices/ios-arm64/libFFmpeg.a" \
    -headers "$work_directory/slices/ios-arm64/Headers" \
    -library "$work_directory/slices/ios-arm64-simulator/libFFmpeg.a" \
    -headers "$work_directory/slices/ios-arm64-simulator/Headers" \
    -output "$xcframework_path"

echo "Created app/Vendor/FFmpeg/FFmpeg.xcframework"
