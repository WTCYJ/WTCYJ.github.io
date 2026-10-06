/**
 * @name ntoh 계열은 함수인가 매크로인가
 * @kind problem
 * @id wtcy/ntoh-kind
 * @problem.severity recommendation
 */
import cpp

from Element e, string kind
where
  e.(FunctionCall).getTarget().getName().regexpMatch("ntoh(s|l|ll)") and kind = "함수 호출"
  or
  e.(MacroInvocation).getMacroName().regexpMatch("ntoh(s|l|ll)") and kind = "매크로 전개"
select e, kind
