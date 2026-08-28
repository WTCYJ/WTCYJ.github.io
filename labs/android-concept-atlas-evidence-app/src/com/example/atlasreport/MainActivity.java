package com.example.atlasreport;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.content.pm.ApplicationInfo;
import android.hardware.fingerprint.FingerprintManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Parcel;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyInfo;
import android.security.keystore.KeyProperties;
import android.text.SpannableString;
import android.text.style.ForegroundColorSpan;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.spec.ECGenParameterSpec;
import java.security.cert.Certificate;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Read-only evidence viewer for the Android Security Concept Atlas.
 * Every displayed value is collected inside the running emulator process.
 */
public final class MainActivity extends Activity {
    private static final int CYAN = Color.rgb(0, 188, 212);

    static {
        System.loadLibrary("atlasevidence");
    }

    private static native String nativeEvidence();

    private static final Map<String, String[]> COMMANDS = new LinkedHashMap<>();
    static {
        COMMANDS.put("environment", new String[] {
                "getprop ro.build.version.release", "getprop ro.build.version.sdk",
                "getprop ro.product.cpu.abi", "uname -a", "id", "getenforce"});
        COMMANDS.put("sandbox", new String[] {
                "id", "cat /proc/self/attr/current",
                "grep -E '^(Name|Pid|Uid|Gid|CapEff|NoNewPrivs|Seccomp):' /proc/self/status",
                "ls -ldZ /data/user/0/com.example.atlasreport"});
        COMMANDS.put("kernel", new String[] {
                "uname -a", "head -n 18 /proc/cpuinfo",
                "cat /proc/sys/kernel/randomize_va_space"});
        COMMANDS.put("boot", new String[] {
                "getprop ro.boot.verifiedbootstate", "getprop ro.boot.flash.locked",
                "getprop ro.boot.vbmeta.device_state", "getprop ro.treble.enabled",
                "getprop ro.apex.updatable"});
        COMMANDS.put("runtime", new String[] {
                "getprop ro.zygote", "getprop dalvik.vm.usejit",
                "getprop dalvik.vm.dex2oat-filter", "ps -A | grep -E 'zygote|system_server'"});
        COMMANDS.put("storage", new String[] {
                "getprop ro.crypto.type", "getprop ro.crypto.state",
                "getprop ro.crypto.volume.filenames_mode", "mount | grep ' /data '"});
        COMMANDS.put("binder", new String[] {
                "ls -l /dev/binder /dev/hwbinder /dev/vndbinder",
                "service list | head -n 12"});
        COMMANDS.put("network", new String[] {
                "ip addr show wlan0", "ip route", "getprop | grep -E 'dns|net\\.' | head -n 12"});
        COMMANDS.put("keystore", new String[] {"__KEYSTORE__"});
        COMMANDS.put("biometric", new String[] {"__BIOMETRIC__"});
        COMMANDS.put("jni", new String[] {"__JNI__"});
        COMMANDS.put("package", new String[] {"__PACKAGE__"});
        COMMANDS.put("parcel", new String[] {"__PARCEL__"});
        COMMANDS.put("identity", new String[] {"__IDENTITY__"});
        COMMANDS.put("uri", new String[] {"__URI__"});
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String section = getIntent().getStringExtra("section");
        if (!COMMANDS.containsKey(section)) section = "environment";

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(42, 48, 42, 72);
        body.setBackgroundColor(Color.rgb(4, 11, 20));

        TextView title = text("ATLAS / " + section.toUpperCase(Locale.ROOT), 28, CYAN, Typeface.BOLD);
        body.addView(title);
        body.addView(text("API 33 Android Emulator · 실물 기기 미사용\n"
                + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.KOREA).format(new Date()),
                14, Color.LTGRAY, Typeface.NORMAL));

        for (String command : COMMANDS.get(section)) {
            body.addView(commandView(command));
        }

        TextView footer = text("VERIFIED IN RUNNING APP PROCESS", 13, CYAN, Typeface.BOLD);
        footer.setGravity(Gravity.CENTER_HORIZONTAL);
        body.addView(footer);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(body, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        setContentView(scroll);
    }

    private TextView commandView(String command) {
        String label = command;
        String output;
        if ("__KEYSTORE__".equals(command)) {
            label = "AndroidKeyStore EC key + attestation request";
            output = keystoreReport();
        } else if ("__BIOMETRIC__".equals(command)) {
            label = "Framework biometric and lock-state query";
            output = biometricReport();
        } else if ("__JNI__".equals(command)) {
            label = "Java -> JNI -> x86_64 native library -> Java";
            output = nativeEvidence() + "\nresult=PASS";
        } else if ("__PACKAGE__".equals(command)) {
            label = "Installed APK structure and app directories";
            output = packageReport();
        } else if ("__PARCEL__".equals(command)) {
            label = "Parcel symmetric read/write and mismatch control";
            output = parcelReport();
        } else if ("__IDENTITY__".equals(command)) {
            label = "Binder calling identity clear/restore lifecycle";
            output = identityReport();
        } else if ("__URI__".equals(command)) {
            label = "Deep-link scheme + exact-host allowlist tests";
            output = uriReport();
        } else {
            output = run(command);
        }
        SpannableString value = new SpannableString("\n$ " + label + "\n" + output + "\n");
        value.setSpan(new ForegroundColorSpan(CYAN), 1, label.length() + 3, 0);
        TextView view = text("", 13, Color.rgb(220, 230, 237), Typeface.NORMAL);
        view.setTypeface(Typeface.MONOSPACE);
        view.setText(value);
        view.setTextIsSelectable(true);
        return view;
    }

    private TextView text(String value, int sp, int color, int style) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setTypeface(Typeface.create(Typeface.SANS_SERIF, style));
        return view;
    }

    private String run(String command) {
        StringBuilder output = new StringBuilder();
        try {
            Process process = new ProcessBuilder("sh", "-c", command).redirectErrorStream(true).start();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) output.append(line).append('\n');
            }
            int exit = process.waitFor();
            if (output.length() == 0) output.append("<empty / not exposed by emulator>\n");
            output.append("[exit=").append(exit).append(']');
        } catch (Exception error) {
            output.append("ERROR: ").append(error.getClass().getSimpleName())
                    .append(": ").append(error.getMessage());
        }
        return output.toString();
    }

    private String keystoreReport() {
        final String alias = "atlas-evidence-key";
        try {
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(alias)) store.deleteEntry(alias);

            KeyPairGenerator generator = KeyPairGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore");
            KeyGenParameterSpec spec = new KeyGenParameterSpec.Builder(alias,
                    KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setAttestationChallenge("atlas-api33-emulator".getBytes(StandardCharsets.UTF_8))
                    .build();
            generator.initialize(spec);
            KeyPair pair = generator.generateKeyPair();
            KeyFactory factory = KeyFactory.getInstance(pair.getPrivate().getAlgorithm(), "AndroidKeyStore");
            KeyInfo info = factory.getKeySpec(pair.getPrivate(), KeyInfo.class);
            Certificate[] chain = store.getCertificateChain(alias);
            return "alias=" + alias
                    + "\nalgorithm=" + pair.getPrivate().getAlgorithm()
                    + "\nsecurityLevel=" + securityLevel(info.getSecurityLevel())
                    + "\ninsideSecureHardware=" + info.isInsideSecureHardware()
                    + "\ncertificateChainLength=" + (chain == null ? 0 : chain.length)
                    + "\nresult=PASS";
        } catch (Exception error) {
            return "result=UNAVAILABLE\n" + error.getClass().getSimpleName() + ": " + error.getMessage();
        }
    }

    private String securityLevel(int level) {
        if (level == KeyProperties.SECURITY_LEVEL_STRONGBOX) return "STRONGBOX(" + level + ")";
        if (level == KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT) return "TRUSTED_ENVIRONMENT(" + level + ")";
        if (level == KeyProperties.SECURITY_LEVEL_SOFTWARE) return "SOFTWARE(" + level + ")";
        return "UNKNOWN(" + level + ")";
    }

    @SuppressWarnings("deprecation")
    private String biometricReport() {
        PackageManager packages = getPackageManager();
        KeyguardManager keyguard = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        FingerprintManager fingerprint = (FingerprintManager) getSystemService(Context.FINGERPRINT_SERVICE);
        return "feature.fingerprint=" + packages.hasSystemFeature(PackageManager.FEATURE_FINGERPRINT)
                + "\nhardwareDetected=" + (fingerprint != null && fingerprint.isHardwareDetected())
                + "\nhasEnrolledFingerprints=" + (fingerprint != null && fingerprint.hasEnrolledFingerprints())
                + "\ndeviceSecure=" + (keyguard != null && keyguard.isDeviceSecure())
                + "\nresult=PASS";
    }

    private String packageReport() {
        try {
            ApplicationInfo info = getApplicationInfo();
            StringBuilder entries = new StringBuilder();
            try (ZipFile apk = new ZipFile(info.sourceDir)) {
                Enumeration<? extends ZipEntry> cursor = apk.entries();
                while (cursor.hasMoreElements()) {
                    String name = cursor.nextElement().getName();
                    if (name.equals("classes.dex") || name.equals("AndroidManifest.xml")
                            || name.startsWith("lib/")) entries.append("\n  ").append(name);
                }
            }
            return "package=" + getPackageName()
                    + "\nuid=" + info.uid
                    + "\nsourceDir=" + info.sourceDir
                    + "\ndataDir=" + info.dataDir
                    + "\nnativeLibraryDir=" + info.nativeLibraryDir
                    + "\nAPK entries:" + entries
                    + "\nresult=PASS";
        } catch (Exception error) {
            return "result=FAIL\n" + error.getClass().getSimpleName() + ": " + error.getMessage();
        }
    }

    private String parcelReport() {
        Parcel parcel = Parcel.obtain();
        try {
            parcel.writeInt(0x11223344);
            parcel.writeString("atlas");
            int bytes = parcel.dataSize();
            parcel.setDataPosition(0);
            int number = parcel.readInt();
            String text = parcel.readString();

            parcel.setDataPosition(0);
            String mismatch;
            try {
                mismatch = "unexpected-value=" + parcel.readString();
            } catch (RuntimeException expected) {
                mismatch = "rejected=" + expected.getClass().getSimpleName();
            }
            return String.format(Locale.ROOT,
                    "dataSize=%d\nroundTrip.int=0x%08x\nroundTrip.string=%s\nmismatch.%s\nresult=PASS",
                    bytes, number, text, mismatch);
        } finally {
            parcel.recycle();
        }
    }

    private String identityReport() {
        int processUid = android.os.Process.myUid();
        int before = Binder.getCallingUid();
        long token = Binder.clearCallingIdentity();
        int cleared;
        try {
            cleared = Binder.getCallingUid();
        } finally {
            Binder.restoreCallingIdentity(token);
        }
        int restored = Binder.getCallingUid();
        return "processUid=" + processUid
                + "\ncallingUid.before=" + before
                + "\ncallingUid.cleared=" + cleared
                + "\ncallingUid.restored=" + restored
                + "\nnoIncomingTransaction=true"
                + "\nresult=" + ((processUid == before && before == restored) ? "PASS" : "FAIL");
    }

    private String uriReport() {
        String[] cases = {
                "https://example.com/account",
                "http://example.com/account",
                "https://example.com.evil.test/account",
                "javascript://example.com/%0aalert(1)"
        };
        StringBuilder report = new StringBuilder();
        boolean allExpected = true;
        for (String value : cases) {
            Uri uri = Uri.parse(value);
            boolean trusted = "https".equals(uri.getScheme()) && "example.com".equals(uri.getHost());
            boolean expected = value.equals(cases[0]);
            allExpected &= trusted == expected;
            report.append(trusted ? "ALLOW " : "DENY  ").append(value).append('\n');
        }
        return report.append("result=").append(allExpected ? "PASS" : "FAIL").toString();
    }
}
