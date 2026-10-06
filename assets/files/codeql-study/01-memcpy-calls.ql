/**
 * @name memcpy 호출 전부
 * @kind problem
 * @id wtcy/memcpy-calls
 * @problem.severity recommendation
 */
import cpp

from FunctionCall call
where call.getTarget().getName() = "memcpy"
select call, "memcpy 크기 인자: " + call.getArgument(2).toString()
