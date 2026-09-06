package com.aas.pkgvis;
import android.app.Activity;
import android.os.Bundle;
import android.content.pm.PackageManager;
import android.content.pm.PackageInfo;
import android.content.pm.ApplicationInfo;
import android.widget.TextView;
import android.widget.ScrollView;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.TypedValue;
import java.util.List;
public class MainActivity extends Activity {
    protected void onCreate(Bundle st) {
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        boolean hasQueries = getResources() != null;   // placeholder
        sb.append("app: com.aas.pkgvis (targetSdk 33)\n");
        sb.append("manifest <queries>: ").append(QUERIES_NOTE).append("\n\n");
        PackageManager pm = getPackageManager();
        List<PackageInfo> all = pm.getInstalledPackages(0);
        int nonSystem = 0;
        StringBuilder names = new StringBuilder();
        for (PackageInfo p : all) {
            ApplicationInfo ai = p.applicationInfo;
            boolean sys = ai != null && (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
            if (!sys) { nonSystem++; if (names.length() < 400) names.append("  ").append(p.packageName).append("\n"); }
        }
        sb.append("getInstalledPackages(0) total = ").append(all.size()).append("\n");
        sb.append("  그중 non-system = ").append(nonSystem).append("\n");
        sb.append("  (visible non-system 목록)\n").append(names).append("\n");
        // 특정 패키지 가시성
        sb.append("getPackageInfo(\"com.insecureshop\") = ");
        try { pm.getPackageInfo("com.insecureshop", 0); sb.append("VISIBLE\n"); }
        catch (PackageManager.NameNotFoundException e) { sb.append("NOT visible (NameNotFoundException)\n"); }
        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(28, 56, 28, 28);
        tv.setTypeface(Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#F0FFF0"));
        sv.addView(tv);
        setContentView(sv);
    }
    static final String QUERIES_NOTE = "<package com.insecureshop>";
}
