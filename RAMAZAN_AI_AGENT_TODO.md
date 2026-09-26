# RAMAZAN AI

## Multi-Agent Autonomous Software Engineering System

**Document:** RAMAZAN_AI_AGENT_TODO.md
**Version:** 1.0
**Purpose:** Yapay zekâ modellerinden oluşan otonom yazılım geliştirme ekibinin çalışma sözleşmesi.

---

### 1. SİSTEMİN AMACI

RAMAZAN AI, tek bir yapay zekânın kod üretmesinden farklı olarak birden fazla yapay zekâ modelini organize eden bir AI Software Engineering Orchestrator sistemidir.

Sistem:
*   Kullanıcı gereksinimini analiz eder.
*   Projeyi parçalara ayırır.
*   Deterministik TODO/task listesi oluşturur.
*   Her task için uygun AI modelini seçer.
*   Worker agent'a görev verir.
*   Üretilen kodu gerçek dosya sistemine uygular.
*   Testleri çalıştırır.
*   Reviewer agent ile kodu denetler.
*   Hataları Worker'a geri gönderir.
*   Gerektiğinde mimariyi değiştirir.
*   Sonsuz döngüyü Circuit Breaker ile engeller.
*   Başarılı task'ları kaydeder.
*   Architecture Decision Record (ADR) oluşturur.
*   Proje tamamlanana kadar task'ları sırayla yürütür.
*   Final audit gerçekleştirir.

**Temel prensip:**
LLM karar verebilir. Kod ise gerçeği belirler.
Bir model "çalışıyor" dediği halde test başarısızsa task başarılı kabul edilmez.

---

### 2. ANA ROL

RAMAZAN AI'nin ana rolü:
**CHIEF SOFTWARE ENGINEERING ORCHESTRATOR**

RAMAZAN AI:
*   Proje yöneticisi
*   Baş mimar
*   Task yöneticisi
*   Model router
*   Agent coordinator
*   Conflict resolver
*   Test coordinator
*   Code reviewer
*   State manager
olarak görev yapar.

Ancak RAMAZAN AI her işi kendisi yapmak zorunda değildir. Uygun olduğunda işi başka agent'lara devreder.

---

### 3. TEMEL FELSEFE

Sistem şu prensiplerle çalışmalıdır:
`PLAN ↓ BREAK DOWN ↓ DELEGATE ↓ IMPLEMENT ↓ TEST ↓ REVIEW ↓ FIX ↓ RETEST ↓ COMMIT ↓ NEXT TASK`

**Asla:**
`PROMPT ↓ CODE ↓ DONE` mantığıyla çalışılmamalıdır.

---

### 4. AGENT ROLLERİ

#### 4.1 ORCHESTRATOR
Ana karar vericidir.
*Önerilen model:* Claude / güçlü reasoning modeli

*Görevleri:*
*   Kullanıcı isteğini anlamak
*   Proje planı oluşturmak
*   Task oluşturmak
*   Task dependency belirlemek
*   Agent seçmek
*   Model seçmek
*   Context hazırlamak
*   Worker çıktılarını değerlendirmek
*   Reviewer sonuçlarını değerlendirmek
*   Conflict çözmek
*   Retry yönetmek
*   Circuit Breaker çalıştırmak
*   Final karar vermek

#### 4.2 ARCHITECT
*Görevi:* Sistem mimarisi, Teknoloji seçimi, Modül sınırları, Veri akışı, API tasarımı, Güvenlik mimarisi, Ölçeklenebilirlik, Dependency kararları üzerinde çalışmaktır.
Architect kararları: `.ramazan/architecture.md` dosyasına yazılmalıdır.

#### 4.3 WORKER
Worker gerçek kodu üretir.
*Örnek modeller:* DeepSeek, Claude, Gemini, Grok, Qwen

Worker'a mümkün olduğunca:
*   ilgili task
*   ilgili dosyalar
*   architecture rules
*   mevcut kod
*   test sonuçları
*   reviewer feedback
verilmelidir. Worker'ın bütün repository'yi gereksiz yere context'e alması engellenmelidir.

#### 4.4 REVIEWER
Reviewer kodu eleştirir. Görevi kod yazmak değildir.
*Şunları kontrol eder:* Correctness, Security, Performance, Maintainability, Architecture, Edge Cases, Error Handling, Testing, Concurrency, Resource Management.
Reviewer sonucu: `APPROVED` veya `CHANGES_REQUIRED` olmalıdır.

#### 4.5 TEST ENGINE
Test Engine LLM değildir. Mümkün olduğunca gerçek araçları çalıştırır.
*Örnek:* `npm test`, `npm run build`, `./gradlew test`, `./gradlew lint`, `pytest`, `cargo test`, `go test ./...`
Test Engine sonucu objektif kabul edilir.

---

### 5. HİYERARŞİ

Agent sistemi:
```text
USER
 │
 ▼
ORCHESTRATOR
 │
 ├── ARCHITECT
 │
 ├── WORKER
 │
 ├── REVIEWER
 │
 └── TEST ENGINE
```
Worker veya Reviewer kendi başına yeni bir ana task oluşturamaz.
Yeni task gerektiğinde: `Agent ↓ Recommendation ↓ Orchestrator ↓ Decision ↓ New Task` akışı kullanılmalıdır.

---

### 6. .ramazan/ DİZİNİ

Her proje kökünde `.ramazan/` klasörü oluşturulmalıdır.

*Önerilen yapı:*
```text
.ramazan/
├── config.json
├── state.json
├── architecture.md
├── requirements.md
├── decisions/
│   ├── ADR-001.md
│   ├── ADR-002.md
│   └── ...
├── tasks/
│   ├── TASK-001.json
│   ├── TASK-002.json
│   └── ...
├── memory/
│   ├── TASK-001.md
│   ├── TASK-002.md
│   └── ...
├── reviews/
│   ├── TASK-001.md
│   └── ...
├── tests/
│   └── latest.json
└── logs/
    └── orchestrator.log
```

---

### 7. STATE.JSON

`state.json` sistemin mevcut durumunu tutar.

*Örnek:*
```json
{
  "project": "drive_manager",
  "version": 1,
  "status": "IN_PROGRESS",
  "currentTask": "TASK-004",
  "completedTasks": [
    "TASK-001",
    "TASK-002",
    "TASK-003"
  ],
  "failedTasks": [],
  "blockedTasks": [],
  "totalTasks": 12,
  "progress": 25,
  "lastUpdated": "2026-09-25T00:00:00Z"
}
```
State dosyası deterministik sistem tarafından yönetilmelidir. LLM doğrudan state'in tamamını kafasına göre değiştirmemelidir.

---

### 8. TASK ŞEMASI

Her task aşağıdaki yapıyı kullanmalıdır:

```json
{
  "id": "TASK-004",
  "title": "Google Drive file copy implementation",
  "description": "Implement file copy functionality.",
  "type": "implementation",
  "priority": "high",
  "complexity": "medium",
  "status": "PENDING",
  "dependencies": [
    "TASK-002"
  ],
  "files": [
    "src/drive/DriveRepository.ts",
    "src/drive/DriveService.ts"
  ],
  "acceptanceCriteria": [
    "Files can be copied successfully.",
    "Errors are handled.",
    "Existing architecture is respected.",
    "Tests are added."
  ],
  "assignedAgent": null,
  "assignedModel": null,
  "retryCount": 0,
  "maxRetries": 3,
  "reviewStatus": "NOT_REVIEWED",
  "testStatus": "NOT_RUN"
}
```

---

### 9. TASK DURUMLARI

*Task lifecycle:*
`PENDING ↓ READY ↓ ASSIGNED ↓ IN_PROGRESS ↓ IMPLEMENTED ↓ TESTING ↓ REVIEWING ↓ APPROVED ↓ COMPLETED`

*Hata durumları:*
`FAILED`, `BLOCKED`, `RETRYING`, `ESCALATED`

---

### 10. TASK GEÇİŞ KURALLARI

*   `PENDING → READY`: Yalnızca dependency'leri tamamlandıysa.
*   `READY → IN_PROGRESS`: Yalnızca uygun agent atandığında.
*   `IMPLEMENTED → TESTING`: Kod değişikliği gerçek dosyalara uygulandıktan sonra.
*   `TESTING → REVIEWING`: Testler başarılıysa gerçekleşir.

Testler başarısızsa: `TESTING ↓ FAILED ↓ RETRYING ↓ WORKER`

---

### 11. ACCEPTANCE CRITERIA

Her implementation task'ı measurable (ölçülebilir) acceptance criteria içermelidir.

*Kötü:* "Drive sistemini güzel yap."
*İyi:*
*   Kullanıcı Drive hesabını seçebilmeli.
*   Dosya listesi alınmalı.
*   Dosya boyutu gösterilmeli.
*   Copy operation başarılı olmalı.
*   API error kullanıcıya anlamlı şekilde gösterilmeli.
*   Unit test bulunmalı.

"Çalışıyor gibi görünüyor" kabul kriteri değildir.

---

### 12. MODEL ROUTING

Her task için en pahalı modeli kullanmak yasaktır.
Task complexity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

*   **LOW:** (boilerplate, basit UI, documentation, basit test, rename/refactor) → Ucuz/hızlı model.
*   **MEDIUM:** (normal feature, API integration, repository, service, component) → Orta seviye model.
*   **HIGH:** (architecture, concurrency, security, complex algorithm, database migration, major refactor) → Güçlü reasoning modeli.
*   **CRITICAL:** (production security, destructive migration, authentication architecture, data corruption risk, major architecture change) → Orchestrator + Architect + Reviewer birlikte çalışmalıdır.

---

### 13. MODEL ROUTER KARARI

Router aşağıdaki faktörleri değerlendirmelidir:
`task complexity`, `task type`, `required capabilities`, `context size`, `tool support`, `cost`, `latency`, `previous success rate`, `failure rate`

*Örnek:*
*   UI boilerplate → cheap worker
*   complex algorithm → strong coding model
*   security review → strong reasoning model
*   architecture decision → orchestrator / architect
*   documentation → cheap model

---

### 14. CONTEXT YÖNETİMİ

Agent'a bütün repository verilmemelidir.
Context şu şekilde oluşturulmalıdır:
`GLOBAL CONTEXT + ARCHITECTURE + RELEVANT TASK + RELEVANT FILES + DEPENDENCY FILES + PREVIOUS TASK MEMORY + TEST RESULTS + REVIEW FEEDBACK`

---

### 15. PROJECT MEMORY

Her tamamlanan task için: `.ramazan/memory/TASK-XXX.md` oluşturulmalıdır.

*Format:*
```markdown
# TASK-004

## Completed
Google Drive file copy functionality implemented.

## Files Changed
- src/drive/DriveService.ts
- src/drive/DriveRepository.ts

## Important Decisions
Drive copy operations use the existing repository abstraction.

## Problems
Initial implementation failed when destination folder was missing.

## Resolution
Added destination validation.

## Tests
12 passed.

## Future Considerations
Large file copy should eventually support resumable operations.
```
Memory kısa ve bilgi yoğun olmalıdır.

---

### 16. ARCHITECTURE DECISION RECORD

Önemli mimari kararlar `.ramazan/decisions/` altına yazılır.

*Örnek:*
```markdown
# ADR-003

## Decision
Use Room for local persistence.

## Context
The application requires offline caching.

## Alternatives
- SQLite
- DataStore
- SQLDelight
- Room

## Reason
Room integrates with the existing Android architecture.

## Consequences
Repository layer will expose Flow-based queries.
```
Bir karar değiştirilecekse eski ADR silinmemelidir. Yeni ADR oluşturulmalıdır.

---

### 17. ARCHITECTURE IMMUTABILITY

`architecture.md` içindeki kararlar worker tarafından sessizce değiştirilemez.
Worker farklı bir yaklaşım önerirse:
`PROPOSAL ↓ ORCHESTRATOR ↓ ARCHITECT REVIEW ↓ DECISION ↓ ADR ↓ architecture.md update` akışı uygulanmalıdır.

---

### 18. REVIEW PROTOKOLÜ

Reviewer yalnızca "LGTM" yazamaz. Şu format kullanılmalıdır:

```json
{
  "status": "CHANGES_REQUIRED",
  "severity": "HIGH",
  "issues": [
    {
      "file": "src/auth/AuthService.ts",
      "line": 87,
      "category": "security",
      "description": "Refresh token is stored insecurely.",
      "requiredFix": "Use secure storage."
    }
  ]
}
```
Reviewer kanıt göstermelidir.

---

### 19. TEST KAPISI

Task'ın tamamlanması için `CODE + TEST + REVIEW` gereklidir.
Sadece modelin "Test edildi." demesi geçerli değildir. Gerçek test çıktısı gerekir.

---

### 20. TEST FAILURE PROTOCOL

Test başarısızsa:
`TEST FAILED ↓ PARSE ERROR ↓ ATTACH ERROR TO TASK ↓ WORKER RETRY`

Worker'a: `Original Task + Changed Files + Test Output + Error Stack + Architecture Rules` verilir.

---

### 21. CIRCUIT BREAKER

Her task için `{"maxRetries": 3}` varsayılan olmalıdır.
3 başarısız denemeden sonra sistem sonsuza kadar retry yapamaz.

---

### 22. CIRCUIT BREAKER SONRASI

Orchestrator üç seçenekten birini seçmelidir:
*   **OPTION A:** Yaklaşımı değiştir. (`Current approach → rejected`, `Alternative architecture → new task`)
*   **OPTION B:** Başka model kullan. (`Worker A → failed`, `Worker B → retry`)
*   **OPTION C:** Human escalation. (`USER_INTERVENTION_REQUIRED`)

---

### 23. HUMAN-IN-THE-LOOP

Aşağıdaki durumlarda kullanıcıya danışılmalıdır:
Destructive database migration, Security-critical decision, Irreversible file deletion, Unknown requirement, Architecture conflict, Repeated failure, External service billing risk, Production deployment, Credential modification.

*Örnek:*
```text
USER_INTERVENTION_REQUIRED
Task: AUTH-004
Problem: Three agents produced incompatible authentication architectures.
Attempts: 3
Options:
A) OAuth + PKCE
B) Existing session architecture
C) Custom token system
Recommendation: Do not proceed automatically. User decision required.
```

---

### 24. CONFLICT RESOLUTION

İki agent farklı görüş verdiyse:
`Agent A ↓ Proposal A` ve `Agent B ↓ Proposal B`
`↓ Orchestrator ↓ Evidence comparison ↓ Tests / benchmarks ↓ Decision`

Model sayısı oy sistemi değildir. "3 agents say A, 1 agent says B" durumunda A otomatik olarak doğru kabul edilmez. Kanıt önceliklidir.

---

### 25. CODE OWNERSHIP

Aynı anda iki Worker aynı dosyayı değiştirmemelidir. Task başlamadan önce `FILE LOCK` oluşturulmalıdır.
Başka task bu dosyalara dokunmak isterse dependency veya coordination gerekir.

---

### 26. GIT STRATEJİSİ

Her başarılı task mümkünse ayrı commit oluşturmalıdır.
*Format:* `feat: ...`, `fix: ...`, `test: ...`, `refactor: ...`
Commit öncesi testler ve review başarılı olmalıdır.

---

### 27. ROLLBACK

Task değişiklikleri testleri bozarsa sistem `git diff`, `git status` ile değişiklikleri analiz eder. Gerekiyorsa `rollback` uygulanabilir. Ancak kullanıcı tarafından yapılmış değişiklikler otomatik olarak silinmemelidir.

---

### 28. TOOL GÜVENLİĞİ

Agent araçları sınırlandırılmalıdır: `read_file`, `write_file`, `edit_file`, `search_code`, `run_tests`, `run_command`, `git_diff`, `git_status`, `git_commit`.
Tehlikeli komutlar (`rm -rf`, `format`, disk operations, credential deletion, production deployment) otomatik çalıştırılmamalıdır.

---

### 29. TERMINAL KOMUTU POLİTİKASI

Worker herhangi bir terminal komutunu çalıştırmadan önce `COMMAND`, `PURPOSE`, `EXPECTED EFFECT`, `RISK` bilgilerini oluşturmalıdır.

---

### 30. TODO PLANLAMA

Yeni proje başladığında Orchestrator:
`Requirements ↓ Architecture ↓ Modules ↓ Dependencies ↓ Tasks ↓ Task Graph` oluşturmalıdır.
Task'lar mümkün olduğunca küçük tutulmalıdır.

---

### 31. TASK DEPENDENCY GRAPH

Orchestrator dependency tamamlanmadan task çalıştırmamalıdır.

---

### 32. PARALLEL TASKS

Birbirine bağımlı olmayan task'lar paralel çalışabilir (örn. UI, Docs, Tests). Ancak aynı dosyaya dokunan task'lar paralel çalıştırılmamalıdır.

---

### 33. TASK PRIORITY

Öncelikler: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
Dependency her zaman priority'den önce gelir.

---

### 34. AGENT PROMPT STANDARDI

Her Worker çağrısı aşağıdaki yapıyı kullanmalıdır:
```text
ROLE: You are a senior software engineer.
PROJECT: [project description]
ARCHITECTURE: [architecture rules]
TASK: [task]
FILES: [relevant files]
CONSTRAINTS: [constraints]
ACCEPTANCE CRITERIA: [criteria]
PREVIOUS ATTEMPT: [if any]
TEST FAILURE: [if any]
REVIEW FEEDBACK: [if any]
REQUIRED OUTPUT:
1. Explain implementation briefly.
2. Modify required files.
3. Add/update tests.
4. Do not modify unrelated files.
5. Report changed files.
6. Report potential risks.
```

---

### 35. WORKER KURALLARI

Worker:
*   Gereksiz dosya değiştirmemelidir.
*   Architecture kurallarına uymalıdır.
*   Test yazmalıdır.
*   Var olan kodu gereksiz yere yeniden yazmamalıdır.
*   Dependency eklemeden önce gerekçelendirmelidir.
*   Security-sensitive kodlarda varsayım yapmamalıdır.
*   Belirsiz gereksinimi kendi kafasına göre büyütmemelidir.
*   Task kapsamının dışına çıkmamalıdır.

---

### 36. REVIEWER KURALLARI

Reviewer:
*   Worker'ı memnun etmeye çalışmamalıdır.
*   Kodun gerçekten çalışıp çalışmadığını kontrol etmelidir.
*   Architecture ihlallerini aramalıdır.
*   Security açıklarını aramalıdır.
*   Edge-case'leri aramalıdır.
*   Gereksiz complexity aramalıdır.
*   Test eksiklerini aramalıdır.
Reviewer'ın görevi "iyi iş" demek değil, hata bulmaktır.

---

### 37. ORCHESTRATOR KURALLARI

Orchestrator:
*   Never trust model output blindly.
*   Never mark task complete without evidence.
*   Never ignore test failures.
*   Never allow infinite retries.
*   Never silently change architecture.
*   Never overwrite unrelated user work.
*   Never expose secrets to unnecessary agents.
*   Never delegate without sufficient context.

---

### 38. SECRET MANAGEMENT

API key, token, password veya credential kaynak kodda, loglarda, memory'de bulunmamalıdır. Environment variable veya secret manager kullanılmalıdır. Agent'lara yalnızca ihtiyaç duydukları credential erişimi verilmelidir.

---

### 39. OBSERVABILITY

Sistem loglamalıdır: `task id`, `agent model`, `start time`, `end time`, `input token`, `output token`, `estimated cost`, `retry count`, `test result`, `review result`, `status`.

---

### 40. BÜTÇE YÖNETİMİ

Proje bazında `maxBudget` tanımlanabilir. Bütçe %80'e geldiğinde Orchestrator uyarılır. Bütçe aşılacaksa `USER_INTERVENTION_REQUIRED` durumu oluşturulur.

---

### 41. MODEL BAŞARIMI

Sistem zaman içerisinde model performansını kaydedebilir (örn. Kodlama başarısı, review tespiti). Bu veriler gelecekte Router tarafından kullanılabilir.

---

### 42. SELF-CRITIQUE

Orchestrator kendi kararını da sorgulamalıdır: "What assumptions am I making?", "What could fail?". Ancak bu sonsuz bir döngüye dönüşmemelidir.

---

### 43. EDGE CASE ANALİZİ

Her önemli task için sorular sorulmalıdır (boş input, network hatası, timeout vb.).

---

### 44. IDEMPOTENCY

Mümkün olan işlemler idempotent tasarlanmalıdır (örn. task retry aynı dosyayı iki kez bozmamalı).

---

### 45. FINAL AUDIT

Bütün task'lar tamamlandıktan sonra `FINAL AUDIT` başlatılır.
Kontroller: Build, Tests, Lint, Security, Architecture, Dependencies, Dead Code, Error Handling, Performance, Documentation, Secrets, Git Status.

---

### 46. FINAL COMPLETION CRITERIA

Proje ancak tüm tasklar bittiğinde, testler geçtiğinde, blocker kalmadığında vb. `PROJECT_STATUS = COMPLETED` olabilir.

---

### 47. FINAL RESPONSE FORMAT

Orchestrator proje sonunda detaylı bir `PROJECT COMPLETED` raporu üretmelidir.

---

### 48. FAILURE REPORT

Proje tamamlanamazsa `PROJECT BLOCKED` raporu üretilmelidir.

---

### 49. ANA ORCHESTRATION ALGORITHM

```python
load project state
while pending tasks exist:
    task = select_next_ready_task()
    analyze task
    determine complexity
    select appropriate agent
    build context
    execute worker
    inspect changes
    run tests
    if tests fail:
        increment retry count
        if retry count < max retries:
            send failure context to worker
            continue
        activate circuit breaker
    run reviewer
    if reviewer rejects:
        increment retry count
        if retry count < max retries:
            send review feedback to worker
            continue
        activate circuit breaker
    if approved:
        update state
        create task memory
        create ADR if necessary
        commit changes
        continue
    run final audit
    if final audit passes:
        mark project completed
    else:
        mark project blocked
```

---

### 50. MUTLAK KURAL

**RAMAZAN AI'nin en önemli kuralı:**
**Model çıktısı gerçek değildir. Sistem çıktısı gerçektir.**
Bir model "Bu kod kesinlikle çalışıyor" dese de test başarısızsa sistem `FAILED` demelidir.

---

### 51. GELİŞTİRME ROADMAP

**PHASE 1 — CORE**
[x] CLI, Project initialization, .ramazan directory, state.json, task engine, filesystem tools, terminal execution

**PHASE 2 — AGENTS & REAL AGENT LOOP**
[x] Multi-turn tool-calling loop (read_file, list_dir, write_file, apply_patch, run_command, run_tests, git_diff)
[x] Mock fallback removal & ModelCallError strict failure semantics
[x] Multi-model role binding (Architect=Claude, Worker=DeepSeek, Reviewer=Grok)
[x] Reviewer real git diff auditing & diff minimality check
[x] Full test suite (93 tests passing)

**PHASE 3 — MEMORY**
[x] architecture.md, ADR, task memory, context builder, project state

**PHASE 4 — AUTONOMY**
[x] automatic task generation, dependency graph, retry engine, circuit breaker, conflict resolution, human escalation

**PHASE 5 — OPTIMIZATION**
[x] model router, budget manager, token tracking, model performance tracking, parallel tasks

**PHASE 6 — PRODUCTION**
[x] security sandbox, permissions, audit logs, rollback, Git integration, CI/CD, dashboard

---

### 52. AGENT'E VERİLECEK ANA TALİMAT

*(Orchestrator System Prompt)*
You are RAMAZAN AI, an autonomous software engineering orchestrator. Your job is not merely to generate code. Your job is to manage a software engineering process involving multiple AI agents.
*   Understand requirements, create deterministic plans, break down tasks.
*   Track dependencies, select appropriate agents.
*   Provide relevant context, implement via tools, run REAL tests.
*   Reject code that fails tests or violates architecture.
*   Manage retries strictly. Escalate unresolved decisions.
*   Maintain project memory and ADRs. Never silently change architecture.
*   Never claim success without evidence. Never expose secrets.
*   The repository and test environment are the source of truth.
*   Prefer evidence over opinions, tests over model confidence.

Your goal is not to produce the most code. Your goal is to produce the smallest correct, tested, maintainable and verifiable solution.

---

### 53. İLK UYGULAMA HEDEFİ

**İlk milestone:**
`RAMAZAN AI v0.1: CLI + Project State + TODO Engine + Filesystem + Terminal + One Worker Model + Tests + Git`
Yalnızca şu döngü kusursuz çalışmalıdır: `TASK ↓ WORKER ↓ CODE ↓ TEST ↓ PASS ↓ COMMIT ↓ NEXT TASK`

---

### 54. BAŞARI TANIMI

RAMAZAN AI bir chatbot değildir. Bir **AI SOFTWARE ENGINEERING ORGANIZATION** olarak tasarlanmıştır. Amacı, gereksinimi alıp, deterministik task'lara bölüp, modelleri görevlendirip, test edip, eleştirip, hataları düzelterek doğrulanmış çalışan yazılım üretmektir.
