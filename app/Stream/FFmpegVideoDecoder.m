#import "FFmpegVideoDecoder.h"

@import FFmpeg;

#import <stdatomic.h>
#import <unistd.h>

static const int64_t FFmpegOpenTimeout = 3 * AV_TIME_BASE;
static const int64_t FFmpegReadTimeout = 2 * AV_TIME_BASE;

typedef struct {
    atomic_bool cancelled;
    atomic_int_fast64_t deadline;
} FFmpegInterruptState;

static int FFmpegInterruptCallback(void *opaque) {
    FFmpegInterruptState *state = opaque;
    if (atomic_load_explicit(&state->cancelled, memory_order_relaxed)) {
        return 1;
    }

    int64_t deadline = atomic_load_explicit(&state->deadline, memory_order_relaxed);
    return deadline > 0 && av_gettime_relative() >= deadline;
}

static NSString *FFmpegErrorDescription(int errorCode) {
    char buffer[AV_ERROR_MAX_STRING_SIZE] = {0};
    if (av_strerror(errorCode, buffer, sizeof(buffer)) < 0) {
        return [NSString stringWithFormat:@"FFmpeg error %d", errorCode];
    }
    return [NSString stringWithUTF8String:buffer];
}

@interface FFmpegVideoDecoder () {
    NSString *_url;
    dispatch_queue_t _decodeQueue;
    dispatch_source_t _frameDeliverySource;
    FFmpegInterruptState _interruptState;
    FFmpegVideoDecoderFrameHandler _frameHandler;
    FFmpegVideoDecoderStatusHandler _statusHandler;
    CGImageRef _pendingFrame;
    NSUInteger _pendingFrameGeneration;
    NSUInteger _generation;
    BOOL _running;
}
@end

@implementation FFmpegVideoDecoder

- (instancetype)initWithURL:(NSString *)url {
    self = [super init];
    if (self) {
        static dispatch_once_t networkInitialization;
        dispatch_once(&networkInitialization, ^{
            avformat_network_init();
        });

        _url = [url copy];
        _decodeQueue = dispatch_queue_create(
            "com.irudnyts.stream.ffmpeg-decoder",
            DISPATCH_QUEUE_SERIAL
        );
        atomic_init(&_interruptState.cancelled, false);
        atomic_init(&_interruptState.deadline, 0);

        _frameDeliverySource = dispatch_source_create(
            DISPATCH_SOURCE_TYPE_DATA_ADD,
            0,
            0,
            dispatch_get_main_queue()
        );
        __weak typeof(self) weakSelf = self;
        dispatch_source_set_event_handler(_frameDeliverySource, ^{
            [weakSelf deliverPendingFrame];
        });
        dispatch_activate(_frameDeliverySource);
    }
    return self;
}

- (void)dealloc {
    atomic_store_explicit(&_interruptState.cancelled, true, memory_order_relaxed);
    dispatch_source_cancel(_frameDeliverySource);
    if (_pendingFrame != NULL) {
        CGImageRelease(_pendingFrame);
    }
}

- (BOOL)isRunning {
    @synchronized (self) {
        return _running;
    }
}

- (void)startWithFrameHandler:(FFmpegVideoDecoderFrameHandler)frameHandler
                statusHandler:(FFmpegVideoDecoderStatusHandler)statusHandler {
    NSUInteger generation;
    @synchronized (self) {
        if (_running) {
            return;
        }

        _running = YES;
        _generation += 1;
        generation = _generation;
        _frameHandler = [frameHandler copy];
        _statusHandler = [statusHandler copy];
    }

    dispatch_async(_decodeQueue, ^{
        @autoreleasepool {
            [self runGeneration:generation];
        }
    });
}

- (void)stop {
    FFmpegVideoDecoderStatusHandler statusHandler;
    NSUInteger stoppedGeneration;
    @synchronized (self) {
        if (!_running) {
            return;
        }

        _running = NO;
        _generation += 1;
        stoppedGeneration = _generation;
        statusHandler = [_statusHandler copy];
        _frameHandler = nil;
        _statusHandler = nil;
        atomic_store_explicit(&_interruptState.cancelled, true, memory_order_relaxed);
        atomic_store_explicit(&_interruptState.deadline, 0, memory_order_relaxed);

        if (_pendingFrame != NULL) {
            CGImageRelease(_pendingFrame);
            _pendingFrame = NULL;
        }
    }

    dispatch_async(dispatch_get_main_queue(), ^{
        @synchronized (self) {
            if (self->_generation != stoppedGeneration) {
                return;
            }
        }
        statusHandler(FFmpegVideoDecoderStatusStopped, nil);
    });
}

- (void)runGeneration:(NSUInteger)generation {
    @synchronized (self) {
        if (_generation != generation || !_running) {
            return;
        }
    }
    atomic_store_explicit(&_interruptState.cancelled, false, memory_order_relaxed);
    atomic_store_explicit(&_interruptState.deadline, 0, memory_order_relaxed);

    BOOL shouldRetry = [_url hasPrefix:@"udp://"];
    [self sendStatus:FFmpegVideoDecoderStatusListening detail:nil generation:generation];

    while (![self isCancelledForGeneration:generation]) {
        NSInteger decodedFrameCount = 0;
        int result = [self decodeOnceForGeneration:generation
                                decodedFrameCount:&decodedFrameCount];

        if ([self isCancelledForGeneration:generation]) {
            return;
        }

        if (!shouldRetry) {
            FFmpegVideoDecoderStatus status =
                result >= 0 && decodedFrameCount > 0
                    ? FFmpegVideoDecoderStatusStopped
                    : FFmpegVideoDecoderStatusFailed;
            NSString *detail = status == FFmpegVideoDecoderStatusFailed
                ? FFmpegErrorDescription(result)
                : nil;
            [self finishGeneration:generation status:status detail:detail];
            return;
        }

        NSString *detail = result < 0 ? FFmpegErrorDescription(result) : nil;
        [self sendStatus:FFmpegVideoDecoderStatusReconnecting
                  detail:detail
              generation:generation];

        for (NSInteger step = 0; step < 10; step += 1) {
            if ([self isCancelledForGeneration:generation]) {
                return;
            }
            usleep(100000);
        }
    }
}

- (int)decodeOnceForGeneration:(NSUInteger)generation
              decodedFrameCount:(NSInteger *)decodedFrameCount {
    AVFormatContext *formatContext = avformat_alloc_context();
    AVCodecContext *codecContext = NULL;
    AVPacket *packet = NULL;
    AVFrame *frame = NULL;
    struct SwsContext *swsContext = NULL;
    AVDictionary *options = NULL;
    int videoStreamIndex = -1;
    int result = AVERROR_UNKNOWN;
    int lastDecodeError = 0;

    if (formatContext == NULL) {
        return AVERROR(ENOMEM);
    }

    formatContext->interrupt_callback.callback = FFmpegInterruptCallback;
    formatContext->interrupt_callback.opaque = &_interruptState;
    const AVInputFormat *inputFormat = av_find_input_format("mpegts");
    if (inputFormat == NULL) {
        result = AVERROR_DEMUXER_NOT_FOUND;
        goto cleanup;
    }

    if ([_url hasPrefix:@"udp://"]) {
        av_dict_set(&options, "fifo_size", "1000000", 0);
        av_dict_set(&options, "overrun_nonfatal", "1", 0);
        av_dict_set(&options, "timeout", "2000000", 0);
        av_dict_set(&options, "rw_timeout", "2000000", 0);
    }

    [self setInterruptDeadlineAfter:FFmpegOpenTimeout];
    result = avformat_open_input(
        &formatContext,
        _url.UTF8String,
        inputFormat,
        &options
    );
    av_dict_free(&options);
    if (result < 0) {
        goto cleanup;
    }

    [self setInterruptDeadlineAfter:FFmpegOpenTimeout];
    result = avformat_find_stream_info(formatContext, NULL);
    if (result < 0) {
        goto cleanup;
    }

    for (unsigned int index = 0; index < formatContext->nb_streams; index += 1) {
        AVCodecParameters *parameters = formatContext->streams[index]->codecpar;
        if (parameters->codec_type == AVMEDIA_TYPE_VIDEO) {
            videoStreamIndex = (int)index;
            break;
        }
    }
    if (videoStreamIndex < 0) {
        result = AVERROR_STREAM_NOT_FOUND;
        goto cleanup;
    }

    AVCodecParameters *parameters = formatContext->streams[videoStreamIndex]->codecpar;
    if (parameters->codec_id != AV_CODEC_ID_H264) {
        result = AVERROR_DECODER_NOT_FOUND;
        goto cleanup;
    }

    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_H264);
    if (codec == NULL) {
        result = AVERROR_DECODER_NOT_FOUND;
        goto cleanup;
    }

    codecContext = avcodec_alloc_context3(codec);
    if (codecContext == NULL) {
        result = AVERROR(ENOMEM);
        goto cleanup;
    }
    result = avcodec_parameters_to_context(codecContext, parameters);
    if (result < 0) {
        goto cleanup;
    }
    result = avcodec_open2(codecContext, codec, NULL);
    if (result < 0) {
        goto cleanup;
    }

    packet = av_packet_alloc();
    frame = av_frame_alloc();
    if (packet == NULL || frame == NULL) {
        result = AVERROR(ENOMEM);
        goto cleanup;
    }

    while (![self isCancelledForGeneration:generation]) {
        [self setInterruptDeadlineAfter:FFmpegReadTimeout];
        result = av_read_frame(formatContext, packet);
        if (result < 0) {
            break;
        }

        if (packet->stream_index == videoStreamIndex) {
            int sendResult = avcodec_send_packet(codecContext, packet);
            if (sendResult < 0 && sendResult != AVERROR(EAGAIN)) {
                lastDecodeError = sendResult;
            } else {
                [self receiveFramesFromCodec:codecContext
                                       frame:frame
                                  swsContext:&swsContext
                                  generation:generation
                           decodedFrameCount:decodedFrameCount
                             lastDecodeError:&lastDecodeError];
            }
        }
        av_packet_unref(packet);
    }

    if (result == AVERROR_EOF && ![self isCancelledForGeneration:generation]) {
        avcodec_send_packet(codecContext, NULL);
        [self receiveFramesFromCodec:codecContext
                               frame:frame
                          swsContext:&swsContext
                          generation:generation
                   decodedFrameCount:decodedFrameCount
                     lastDecodeError:&lastDecodeError];
        result = *decodedFrameCount > 0 ? 0 : AVERROR_INVALIDDATA;
    } else if (*decodedFrameCount == 0 && lastDecodeError < 0) {
        result = lastDecodeError;
    }

cleanup:
    atomic_store_explicit(&_interruptState.deadline, 0, memory_order_relaxed);
    av_dict_free(&options);
    sws_freeContext(swsContext);
    av_frame_free(&frame);
    av_packet_free(&packet);
    avcodec_free_context(&codecContext);
    avformat_close_input(&formatContext);
    return result;
}

- (void)receiveFramesFromCodec:(AVCodecContext *)codecContext
                         frame:(AVFrame *)frame
                    swsContext:(struct SwsContext **)swsContext
                    generation:(NSUInteger)generation
             decodedFrameCount:(NSInteger *)decodedFrameCount
               lastDecodeError:(int *)lastDecodeError {
    while (![self isCancelledForGeneration:generation]) {
        int result = avcodec_receive_frame(codecContext, frame);
        if (result == AVERROR(EAGAIN) || result == AVERROR_EOF) {
            return;
        }
        if (result < 0) {
            *lastDecodeError = result;
            return;
        }

        CGImageRef image = [self newImageFromFrame:frame swsContext:swsContext];
        if (image != NULL) {
            if (*decodedFrameCount == 0) {
                [self sendStatus:FFmpegVideoDecoderStatusPlaying
                          detail:nil
                      generation:generation];
            }
            *decodedFrameCount += 1;
            [self enqueueFrame:image generation:generation];
            CGImageRelease(image);
        }
        av_frame_unref(frame);
    }
}

- (CGImageRef)newImageFromFrame:(AVFrame *)frame
                     swsContext:(struct SwsContext **)swsContext CF_RETURNS_RETAINED {
    if (frame->width <= 0 || frame->height <= 0) {
        return NULL;
    }

    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    CGBitmapInfo bitmapInfo = (CGBitmapInfo)(
        (uint32_t)kCGBitmapByteOrder32Little |
        (uint32_t)kCGImageAlphaPremultipliedFirst
    );
    CGContextRef bitmapContext = CGBitmapContextCreate(
        NULL,
        (size_t)frame->width,
        (size_t)frame->height,
        8,
        0,
        colorSpace,
        bitmapInfo
    );
    CGColorSpaceRelease(colorSpace);
    if (bitmapContext == NULL) {
        return NULL;
    }

    *swsContext = sws_getCachedContext(
        *swsContext,
        frame->width,
        frame->height,
        (enum AVPixelFormat)frame->format,
        frame->width,
        frame->height,
        AV_PIX_FMT_BGRA,
        SWS_BILINEAR,
        NULL,
        NULL,
        NULL
    );
    if (*swsContext == NULL) {
        CGContextRelease(bitmapContext);
        return NULL;
    }

    uint8_t *destinationData[4] = {
        CGBitmapContextGetData(bitmapContext), NULL, NULL, NULL
    };
    int destinationLinesize[4] = {
        (int)CGBitmapContextGetBytesPerRow(bitmapContext), 0, 0, 0
    };
    sws_scale(
        *swsContext,
        (const uint8_t *const *)frame->data,
        frame->linesize,
        0,
        frame->height,
        destinationData,
        destinationLinesize
    );

    CGImageRef image = CGBitmapContextCreateImage(bitmapContext);
    CGContextRelease(bitmapContext);
    return image;
}

- (void)enqueueFrame:(CGImageRef)image generation:(NSUInteger)generation {
    @synchronized (self) {
        if (_generation != generation || !_running) {
            return;
        }
        if (_pendingFrame != NULL) {
            CGImageRelease(_pendingFrame);
        }
        _pendingFrame = CGImageRetain(image);
        _pendingFrameGeneration = generation;
    }
    dispatch_source_merge_data(_frameDeliverySource, 1);
}

- (void)deliverPendingFrame {
    CGImageRef image = NULL;
    FFmpegVideoDecoderFrameHandler frameHandler;
    @synchronized (self) {
        if (_pendingFrame == NULL || _pendingFrameGeneration != _generation) {
            return;
        }
        image = _pendingFrame;
        _pendingFrame = NULL;
        frameHandler = [_frameHandler copy];
    }

    if (frameHandler != nil) {
        frameHandler(image);
    }
    CGImageRelease(image);
}

- (void)setInterruptDeadlineAfter:(int64_t)interval {
    atomic_store_explicit(
        &_interruptState.deadline,
        av_gettime_relative() + interval,
        memory_order_relaxed
    );
}

- (BOOL)isCancelledForGeneration:(NSUInteger)generation {
    if (atomic_load_explicit(&_interruptState.cancelled, memory_order_relaxed)) {
        return YES;
    }
    @synchronized (self) {
        return generation != _generation;
    }
}

- (void)sendStatus:(FFmpegVideoDecoderStatus)status
             detail:(NSString * _Nullable)detail
         generation:(NSUInteger)generation {
    dispatch_async(dispatch_get_main_queue(), ^{
        FFmpegVideoDecoderStatusHandler statusHandler;
        @synchronized (self) {
            if (self->_generation != generation) {
                return;
            }
            statusHandler = [self->_statusHandler copy];
        }
        if (statusHandler != nil) {
            statusHandler(status, detail);
        }
    });
}

- (void)finishGeneration:(NSUInteger)generation
                   status:(FFmpegVideoDecoderStatus)status
                   detail:(NSString * _Nullable)detail {
    @synchronized (self) {
        if (_generation != generation) {
            return;
        }
        _running = NO;
    }
    [self sendStatus:status detail:detail generation:generation];
}

@end
