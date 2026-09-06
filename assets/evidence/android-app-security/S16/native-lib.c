#include <jni.h>
#include <string.h>
#include <android/log.h>

/* 왜 네이티브를 분석하나: 비밀·로직이 .so 안에 있을 수 있다 */
static const char* secret(void) { return "N4T1V3_S3CR3T_x9"; }

/* 이름 규칙으로 연결되는 네이티브 메서드 (Java_<pkg>_<class>_<method>) */
JNIEXPORT jstring JNICALL
Java_com_aas_jni_MainActivity_getNativeSecret(JNIEnv* env, jobject thiz) {
    return (*env)->NewStringUTF(env, secret());
}

/* RegisterNatives 로 동적 등록되는 네이티브 메서드 (이름 규칙 안 씀) */
static jstring native_flag(JNIEnv* env, jobject thiz) {
    return (*env)->NewStringUTF(env, "flag{registered_via_JNI_OnLoad}");
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
    JNIEnv* env;
    if ((*vm)->GetEnv(vm, (void**)&env, JNI_VERSION_1_6) != JNI_OK) return -1;
    jclass clazz = (*env)->FindClass(env, "com/aas/jni/MainActivity");
    static const JNINativeMethod methods[] = {
        { "nativeFlag", "()Ljava/lang/String;", (void*)native_flag }
    };
    (*env)->RegisterNatives(env, clazz, methods, 1);
    __android_log_print(ANDROID_LOG_INFO, "aasjni", "JNI_OnLoad: RegisterNatives(nativeFlag)");
    return JNI_VERSION_1_6;
}
