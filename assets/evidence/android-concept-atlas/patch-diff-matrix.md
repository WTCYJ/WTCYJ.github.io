# Patch-diff and reproducibility matrix

Captured: 2026-08-29 02:14:22 +09:00

```text
## normal
before exit=0
before offset=10 length=20 total=100 end=30 decision=ACCEPT
after exit=0
after offset=10 length=20 total=100 decision=ACCEPT
## boundary
before exit=0
before offset=80 length=20 total=100 end=100 decision=ACCEPT
after exit=0
after offset=80 length=20 total=100 decision=ACCEPT
## range-error
before exit=1
before offset=90 length=20 total=100 end=110 decision=REJECT
after exit=1
after offset=90 length=20 total=100 decision=REJECT
## overflow
before exit=134
C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-research-method\length_check_before.c:10:26: runtime error: signed integer overflow: 2147483640 + 16 cannot be represented in type 'int32_t' (aka 'int')
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-research-method\length_check_before.c:10:26 in
Aborted
after exit=1
after offset=2147483640 length=16 total=4096 decision=REJECT

patch-diff-matrix=PASS
```

run1_sha256=affabb1a8cceca929c845acaa2c4cfa8af780dbb0357feed14865d3f5f809bf9

run2_sha256=affabb1a8cceca929c845acaa2c4cfa8af780dbb0357feed14865d3f5f809bf9

reproducible=True
