import FFmpeg

enum FFmpegVersion {
    static var string: String {
        String(cString: av_version_info())
    }
}
