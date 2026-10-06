/**
 * @name 네트워크 값이 memcpy 크기로 흐른다 (식 단위 상한 검사, 부호 고려)
 * @kind path-problem
 * @id wtcy/ntoh-to-memcpy-bounded
 * @problem.severity warning
 */
import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import semmle.code.cpp.controlflow.Guards
import semmle.code.cpp.valuenumbering.HashCons
import semmle.code.cpp.rangeanalysis.SimpleRangeAnalysis
import NetworkByteSwap

/**
 * e 와 같은 모양의 식이, e 를 지키는 비교문의 '작은 쪽'에 들어 있다.
 * `a > b` 가 거짓인 쪽이면 a 가, `a < b` 가 참인 쪽이면 a 가 상한을 받은 것으로 본다.
 * 음수가 될 수 있는 값은 상한 검사를 그냥 통과하므로 인정하지 않는다. 타입이 아니라 범위 분석으로 본다.
 * ponytail: hashCons 는 두 식 사이의 쓰기를 보지 않는다. 오탐보다 누락이 문제가 되면 GlobalValueNumbering 으로 바꾼다.
 */
predicate boundedAbove(Expr e) {
  lowerBound(e) >= 0 and
  exists(GuardCondition g, RelationalOperation cmp, boolean branch, Expr side, Expr sub |
    g = cmp and
    g.controls(e.getBasicBlock(), branch) and
    (if branch = true then side = cmp.getLesserOperand() else side = cmp.getGreaterOperand()) and
    sub = side.getAChild*() and
    hashCons(sub) = hashCons(e)
  )
}

module NtohConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { n.asExpr() instanceof NetworkByteSwap }

  predicate isSink(DataFlow::Node n) {
    exists(FunctionCall c | c.getTarget().getName() = "memcpy" and n.asExpr() = c.getArgument(2))
  }

  predicate isBarrier(DataFlow::Node n) { boundedAbove(n.asExpr()) }
}

module NtohFlow = TaintTracking::Global<NtohConfig>;
import NtohFlow::PathGraph

from NtohFlow::PathNode src, NtohFlow::PathNode sink
where NtohFlow::flowPath(src, sink)
select sink.getNode(), src, sink, "$@ 에서 온 값이 상한 검사 없이 memcpy 크기가 된다",
  src.getNode(), "네트워크 값"
