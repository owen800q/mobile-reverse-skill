#import <UIKit/UIKit.h>

__attribute__((naked, noinline, used, visibility("default")))
uint64_t qbdi_fixture_target(uint64_t value) {
    __asm__ volatile(
        "add x0, x0, #7\n"
        "eor x0, x0, #0xff\n"
        "ret\n"
        ".globl _qbdi_fixture_target_end\n"
        "_qbdi_fixture_target_end:\n"
    );
}

@interface FixtureDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow *window;
@end

@implementation FixtureDelegate

- (BOOL)application:(UIApplication *)application
        didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    UIViewController *controller = [UIViewController new];
    controller.view.backgroundColor = UIColor.systemBackgroundColor;

    UILabel *label = [[UILabel alloc] initWithFrame:controller.view.bounds];
    label.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    label.textAlignment = NSTextAlignmentCenter;
    label.numberOfLines = 0;
    label.text = @"QBDI PlayCover fixture\nwaiting for trace";
    [controller.view addSubview:label];

    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 2 * NSEC_PER_SEC),
                   dispatch_get_main_queue(), ^{
        uint64_t result = qbdi_fixture_target(0x1234);
        label.text = [NSString stringWithFormat:@"trace target returned 0x%llx", result];
        NSLog(@"QBDI_FIXTURE_RESULT=0x%llx", result);
    });
    return YES;
}

@end

int main(int argc, char **argv) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass(FixtureDelegate.class));
    }
}
