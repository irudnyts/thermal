#import <CoreGraphics/CoreGraphics.h>
#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

typedef NS_ENUM(NSInteger, FFmpegVideoDecoderStatus) {
    FFmpegVideoDecoderStatusStopped,
    FFmpegVideoDecoderStatusListening,
    FFmpegVideoDecoderStatusPlaying,
    FFmpegVideoDecoderStatusReconnecting,
    FFmpegVideoDecoderStatusFailed,
};

typedef void (^FFmpegVideoDecoderFrameHandler)(CGImageRef image);
typedef void (^FFmpegVideoDecoderStatusHandler)(
    FFmpegVideoDecoderStatus status,
    NSString * _Nullable detail
);

@interface FFmpegVideoDecoder : NSObject

@property (atomic, readonly, getter=isRunning) BOOL running;

- (instancetype)initWithURL:(NSString *)url NS_DESIGNATED_INITIALIZER;
- (instancetype)init NS_UNAVAILABLE;

- (void)startWithFrameHandler:(FFmpegVideoDecoderFrameHandler)frameHandler
                statusHandler:(FFmpegVideoDecoderStatusHandler)statusHandler;
- (void)stop;

@end

NS_ASSUME_NONNULL_END
