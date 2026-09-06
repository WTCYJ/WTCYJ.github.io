package com.aas.obf;
import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.ScrollView;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.TypedValue;
import java.lang.reflect.Method;
public class MainActivity extends Activity {
    String getApiKey() { return "APIKEY-9f3c-SECRET"; }
    boolean verifyIntegrity() { return true; }
    String buildSignatureHash() { return "sha256:deadbeef..."; }
    protected void onCreate(Bundle st){
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        sb.append("이 클래스의 선언 메서드 (리플렉션):\n");
        for (Method m : MainActivity.class.getDeclaredMethods()) {
            sb.append("  ").append(m.getName()).append("()\n");
        }
        sb.append("\ngetApiKey() 반환값     = ").append(getApiKey()).append("\n");
        sb.append("verifyIntegrity()      = ").append(verifyIntegrity()).append("\n");
        sb.append("buildSignatureHash()   = ").append(buildSignatureHash()).append("\n");
        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(28,56,28,28);
        tv.setTypeface(Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#F3E8FF"));
        sv.addView(tv);
        setContentView(sv);
    }
}
