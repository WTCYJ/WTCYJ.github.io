/**
 * @name 네트워크 값이 memcpy 크기로 흐른다 (상한 검사 반영)
 * @kind path-problem
 * @id wtcy/ntoh-to-memcpy-guarded
 * @problem.severity warning
 */
import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import semmle.code.cpp.controlflow.Guards
import NetworkByteSwap

/**
 * 변수 v 를 읽는 식 e 가, v 의 상한을 확인하는 비교문이 지켜 주는 블록 안에 있다.
 * ponytail: 비교 방향과 비교 대상 값의 크기는 보지 않는다. 오탐이 문제가 되면 SimpleRangeAnalysis 의 upperBound 로 바꾼다.
 */
predicate guardedByUpperBound(Expr e) {
  exists(GuardCondition g, Variable v, RelationalOperation cmp, boolean branch |
    g = cmp and
    cmp.getAnOperand() = v.getAnAccess() and
    e = v.getAnAccess() and
    g.controls(e.getBasicBlock(), branch) and
    // 큰 쪽(GreatestOperand)이 v 가 아닌 분기, 즉 v 가 상한보다 작다고 확인된 쪽만 인정한다
    (if cmp.getGreaterOperand() = v.getAnAccess() then branch = false else branch = true)
  )
}

module NtohConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { n.asExpr() instanceof NetworkByteSwap }

  predicate isSink(DataFlow::Node n) {
    exists(FunctionCall c | c.getTarget().getName() = "memcpy" and n.asExpr() = c.getArgument(2))
  }

  predicate isBarrier(DataFlow::Node n) { guardedByUpperBound(n.asExpr()) }
}

module NtohFlow = TaintTracking::Global<NtohConfig>;
import NtohFlow::PathGraph

from NtohFlow::PathNode src, NtohFlow::PathNode sink
where NtohFlow::flowPath(src, sink)
select sink.getNode(), src, sink, "$@ 에서 온 값이 상한 검사 없이 memcpy 크기가 된다",
  src.getNode(), "네트워크 값"
