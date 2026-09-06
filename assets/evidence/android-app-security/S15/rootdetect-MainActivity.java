package com.aas.rootdetect;
import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.os.Debug;
import android.widget.TextView;
import android.widget.ScrollView;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.TypedValue;
import java.io.File;
import java.io.BufferedReader;
import java.io.FileReader;
public class MainActivity extends Activity {
    static boolean fileExists(String p){ return new File(p).exists(); }
    static boolean suOnPath() {
        String[] paths = {"/system/bin/su","/system/xbin/su","/sbin/su","/su/bin/su",
                          "/system/app/Superuser.apk","/data/local/tmp/su","/data/local/su"};
        for (String p: paths) if (fileExists(p)) return true;
        return false;
    }
    static boolean testKeys(){ String t=Build.TAGS; return t!=null && t.contains("test-keys"); }
    static boolean roDebuggable(){ return "1".equals(getProp("ro.debuggable")); }
    static boolean roSecure0(){ return "0".equals(getProp("ro.secure")); }
    static boolean fridaArtifacts(){
        // 열려 있는 포트/라이브러리 흔적 (대표적 탐지 시도)
        try {
            BufferedReader br = new BufferedReader(new FileReader("/proc/self/maps"));
            String line; while ((line=br.readLine())!=null){ if (line.contains("frida")||line.contains("gum-js")) { br.close(); return true; } }
            br.close();
        } catch (Exception e){}
        return false;
    }
    static String getProp(String k){
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"getprop", k});
            BufferedReader br = new BufferedReader(new java.io.InputStreamReader(p.getInputStream()));
            String v = br.readLine(); br.close(); return v==null?"":v.trim();
        } catch (Exception e){ return ""; }
    }
    void row(StringBuilder sb, String name, boolean flagged, String detail){
        sb.append(flagged ? "[X] " : "[ ] ").append(name);
        if (detail!=null) sb.append("  (").append(detail).append(")");
        sb.append("\n");
    }
    protected void onCreate(Bundle st){
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        sb.append("client-side root / debug detection (checks)\n");
        sb.append("device = ").append(Build.MODEL).append(" / TAGS=").append(Build.TAGS).append("\n\n");
        boolean su = suOnPath(), tk = testKeys(), dbg = Debug.isDebuggerConnected(),
                rod = roDebuggable(), rs0 = roSecure0(), fr = fridaArtifacts();
        row(sb, "su binary on known paths", su, null);
        row(sb, "Build.TAGS = test-keys", tk, Build.TAGS);
        row(sb, "ro.debuggable = 1", rod, "getprop");
        row(sb, "ro.secure = 0", rs0, "getprop");
        row(sb, "debugger attached", dbg, null);
        row(sb, "frida in /proc/self/maps", fr, null);
        int flags = (su?1:0)+(tk?1:0)+(rod?1:0)+(rs0?1:0)+(dbg?1:0)+(fr?1:0);
        sb.append("\n=> flagged ").append(flags).append(" / 6\n");
        sb.append(flags>0 ? "verdict: COMPROMISED (client-side)\n" : "verdict: clean (client-side)\n");
        sb.append("\n주의: 이 판정은 전부 이 프로세스 안에서 난다.\n");
        sb.append("에뮬레이터(userdebug/test-keys)는 실제 위협이 아닌데도\n");
        sb.append("여러 체크가 켜진다 = false positive. 그리고 각 체크는\n");
        sb.append("Frida 로 반환만 뒤집으면 무력화된다(S14).\n");
        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(28,56,28,28);
        tv.setTypeface(Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#FFF6E5"));
        sv.addView(tv);
        setContentView(sv);
    }
}
