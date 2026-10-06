/**
 * @kind problem
 * @id wtcy/dbg-tainted-globals
 * @problem.severity recommendation
 */
import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import NetworkByteSwap

module C implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) {
    n.asExpr() instanceof NetworkByteSwap and
    n.getLocation().getFile().getBaseName() = "net.c" and
    n.getLocation().getStartLine() = 982
  }

  predicate isSink(DataFlow::Node n) {
    exists(Assignment a | n.asExpr() = a.getRValue() |
      a.getLValue().(VariableAccess).getTarget() instanceof GlobalOrNamespaceVariable
      or
      a.getLValue().(VariableAccess).getTarget().(LocalVariable).isStatic()
    )
  }
}

module F = TaintTracking::Global<C>;

from DataFlow::Node src, DataFlow::Node sink, Assignment a
where F::flow(src, sink) and sink.asExpr() = a.getRValue()
select sink, a.getLValue().toString() + " = ... in " + a.getEnclosingFunction().getName()
