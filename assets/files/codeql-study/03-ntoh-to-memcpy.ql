/**
 * @name 네트워크 값이 memcpy 크기로 흐른다
 * @kind path-problem
 * @id wtcy/ntoh-to-memcpy
 * @problem.severity warning
 */
import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import NetworkByteSwap

module NtohConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { n.asExpr() instanceof NetworkByteSwap }

  predicate isSink(DataFlow::Node n) {
    exists(FunctionCall c | c.getTarget().getName() = "memcpy" and n.asExpr() = c.getArgument(2))
  }
}

module NtohFlow = TaintTracking::Global<NtohConfig>;
import NtohFlow::PathGraph

from NtohFlow::PathNode src, NtohFlow::PathNode sink
where NtohFlow::flowPath(src, sink)
select sink.getNode(), src, sink, "$@ 에서 온 값이 검사 없이 memcpy 크기가 된다", src.getNode(),
  "네트워크 값"
