import cpp

/** 네트워크 바이트 순서를 뒤집는 식. 빌드 옵션에 따라 함수일 수도 매크로일 수도 있다. */
class NetworkByteSwap extends Expr {
  NetworkByteSwap() {
    this.(FunctionCall).getTarget().getName().regexpMatch("ntoh(s|l|ll)")
    or
    exists(MacroInvocation mi |
      mi.getMacroName().regexpMatch("ntoh(s|l|ll)") and this = mi.getExpr()
    )
  }
}
