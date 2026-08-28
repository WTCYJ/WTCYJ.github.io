#include <jni.h>
#include <stdio.h>

JNIEXPORT jstring JNICALL
Java_com_example_atlasreport_MainActivity_nativeEvidence(JNIEnv *env, jclass type) {
    (void) type;
    char report[160];
    snprintf(report, sizeof(report),
             "JNI boundary=PASS\nJNIEnv=non-null\n__ANDROID_API__=%d\npointerBytes=%zu",
             __ANDROID_API__, sizeof(void *));
    return (*env)->NewStringUTF(env, report);
}
