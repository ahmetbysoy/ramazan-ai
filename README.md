# RAMAZAN AI

> **Multi-Agent Autonomous Software Engineering Orchestrator**  
> *"LLM karar verebilir. Kod ise gerçeği belirler."*

---

## 1. Genel Bakış

**RAMAZAN AI**, tek bir yapay zekânın rastgele kod üretmesinden farklı olarak birden fazla uzmanlaşmış yapay zekâ modelini organize eden bir **Chief Software Engineering Orchestrator** sistemidir.

### Temel Çalışma Döngüsü:
```text
PLAN ↓ BREAK DOWN ↓ DELEGATE ↓ IMPLEMENT ↓ TEST ↓ REVIEW ↓ FIX ↓ RETEST ↓ COMMIT ↓ NEXT TASK
```
**Asla:** `PROMPT ↓ CODE ↓ DONE` mantığıyla çalışmaz.

---

## 2. Agent Rolleri ve Hiyerarşi

```text
                  USER
                   │
                   ▼
              ORCHESTRATOR
         (Chief Decision Maker)
                   │
    ┌──────────────┼──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
ARCHITECT        WORKER       REVIEWER      TEST ENGINE
 (ADR/System)  (Code Writer) (Code Auditor)  (Objective pytest/npm)
```

1. **Orchestrator**: Yüksek seviyeli planlama, görev ayrıştırma (WBS), bağımlılık yönetimi, model yönlendirme ve Circuit Breaker yönetimi.
2. **Architect**: Sistem mimarisi (`.ramazan/architecture.md`), modül sınırları ve Mimari Karar Kayıtları (`.ramazan/decisions/ADR-XXX.md`).
3. **Worker**: Sadece belirlenen dosyalara odaklanarak atomik kod ve test üreten geliştirici agent. Dosya kitleme (File Lock) protokolüne tabidir.
4. **Reviewer**: Kodu denetleyen, güvenlik, doğruluk, mimari uyum ve sınır durumları inceleyen bağımsız eleştirmen. Yapılandırılmış JSON çıktısı (`APPROVED` veya `CHANGES_REQUIRED`) üretir.
5. **Test Engine**: Kesinlikle LLM değildir. Gerçek test araçlarını (`pytest`, `npm test`, `./gradlew test`) çalıştırarak nesnel sonuç üretir.

---

## 3. Klasör Yapısı

```text
/home/user/
├── RAMAZAN_AI_AGENT_TODO.md      # Ana sözleşme ve teknik şartname
├── pyproject.toml                # Paket konfigürasyonu
├── setup.py                      # Paket kurulumu
├── requirements.txt              # Bağımlılıklar
├── README.md                     # Sistem dokümantasyonu
├── .ramazan/                     # Deterministik Orchestrator çalışma alanı
│   ├── config.json               # Model, bütçe ve araç ayarları
│   ├── state.json                # Deterministik proje durumu ve görev takibi
│   ├── architecture.md           # Sistem mimarisi ve değişmezlik kuralları
│   ├── requirements.md           # Proje gereksinimleri
│   ├── decisions/                # Mimari Karar Kayıtları (ADR-001.md, ...)
│   ├── tasks/                    # Görev tanımları (TASK-001.json, ...)
│   ├── memory/                   # Görev hafızaları (TASK-001.md, ...)
│   ├── reviews/                  # Kod inceleme raporları (TASK-001.md, ...)
│   ├── tests/                    # Nesnel test motoru çıktıları (latest.json)
│   └── logs/                     # Sistem ve yürütme günlükleri
├── ramazan/                      # RAMAZAN AI çekirdek Python paketi
│   ├── cli.py                    # Typer & Rich CLI arayüzü
│   ├── config.py                 # Yapılandırma yöneticisi
│   ├── schemas/                  # Pydantic veri modelleri (Task, State, Review, ADR)
│   ├── core/                     # Orchestrator, TaskEngine, CircuitBreaker, Router
│   ├── agents/                   # Orchestrator, Architect, Worker, Reviewer ajanları
│   ├── llm/                      # LiteLLM evrensel istemcisi & Bütçe/Maliyet takibi
│   ├── tools/                    # Dosya sistemi, terminal, test motoru, git yöneticisi, patch motoru
│   └── audit/                    # Nihai denetim (Final Audit) motoru
└── tests/                        # Kapsamlı test paketi (93 otomatik test, %100 passing)
```

---

## 4. Kurulum

Sistem bağımlılıklarını kurmak ve `ramazan` CLI komutunu etkinleştirmek için:

```bash
pip install -r requirements.txt
pip install -e .
```

Kurulumun doğrulanması:
```bash
ramazan --help
pytest -v
```

---

## 5. CLI Komutları

| Komut | Açıklama |
|---|---|
| `ramazan init` | Mevcut dizinde `.ramazan` çalışma alanı yapısını ve git deposunu ilklendirir. |
| `ramazan doctor` | Sistem sağlığı, geçerli model isimleri ve katı şema teşhisini çalıştırır. |
| `ramazan ui` / `ramazan web` | Kullanıcı dostu Web Arayüzünü (`http://0.0.0.0:8000`) başlatır. |
| `ramazan configure` | Akıllı API anahtarı algılama, rol eşleştirme (`--architect`, `--worker`, `--reviewer`) ve otonomi modu sihirbazı. |
| `ramazan status` | Proje durumunu, ilerleme yüzdesini, aktif görevleri ve görev tablosunu gösterir. |
| `ramazan plan` | `requirements.md` içeriğini analiz ederek DAG tabanlı görev grafiği oluşturur. |
| `ramazan run` | Tüm görevler tamamlanana veya bloklanana kadar ana orkestrasyon döngüsünü çalıştırır. |
| `ramazan step` | Sırada hazır bekleyen tek bir görevi uçtan uca çalıştırır. |
| `ramazan test` | Nesnel Test Motorunu çalıştırır ve sonuçları `.ramazan/tests/latest.json`'a kaydeder. |
| `ramazan audit` | Test, güvenlik, gizli anahtar ve git doğrulamalarını içeren Nihai Kalite Kapısını (Final Audit) çalıştırır. |

---

## 6. Temel Mekanizmalar

### 6.1 Model Yönlendirme (Model Router)
Her görev için en pahalı modeli kullanmak yasaktır:
- **LOW:** Dokümantasyon, basit UI, boilerplate → Hızlı ve ucuz modeller (`gpt-4o-mini`, `claude-3-5-haiku`).
- **MEDIUM:** Servis katmanı, API entegrasyonu, repolar → Orta segment modeller.
- **HIGH:** Karmaşık algoritmalar, eşzamanlılık, güvenlik → Güçlü akıl yürütme modelleri (`claude-3-7-sonnet`, `gpt-4o`).
- **CRITICAL:** Prodüksiyon güvenliği, veri tabanı geçişleri → Ensemble (Orchestrator + Architect + Reviewer).

### 6.2 Circuit Breaker & Human-In-The-Loop
- Her görev için varsayılan `maxRetries: 3` uygulanır.
- 3 başarısız denemenin ardından döngü kesilir:
  - **Option A:** Yaklaşımı değiştir ve yeni alt görev oluştur.
  - **Option B:** Alternatif modele geçiş yap.
  - **Option C:** Kritik hatalarda insan müdahalesi talep et (`USER_INTERVENTION_REQUIRED`).

### 6.3 Güvenlik ve Gizli Anahtar Yönetimi
- Kaynak kodda, loglarda veya hafızada API anahtarı, şifre ve token bulunması yasaktır.
- `rm -rf /`, disk biçimlendirme ve yetkisiz terminal komutları güvenlik katmanı tarafından engellenir.
- Her terminal komutu için `COMMAND`, `PURPOSE`, `EXPECTED EFFECT`, `RISK` zorunludur.

### 6.4 Git Entegrasyonu & Diff İnceleme
- Başarılı olan her görev için testler ve review onayından sonra otomatik atomik commit (`feat: [TASK-001] ...`) oluşturulur.
- Testler başarısız olursa güvenli rollback uygulanır.
- Reviewer, `git diff` ile intent-to-add edilmiş dosyalar dahil gerçek diff'i satır satır inceler ve gereksiz yeniden yazımları (Diff Minimality) denetler.

### 6.5 Çoklu Model Rol Dağılımı (Multi-Model Architecture)
RAMAZAN AI, sektör standardı multi-agent iş bölümü prensibiyle optimize edilmiştir:
- **Architect (Claude):** Sistem mimarisi, gereksinim analizi, DAG planlama ve teknik tasarım (`claude-3-7-sonnet`).
- **Worker (DeepSeek):** Çok turlu (multi-turn) tool loop ile kodlama, minimal diff yamaları ve test üretimi (`deepseek/deepseek-chat`).
- **Reviewer (Grok / Claude):** Gerçek `git diff` denetimi, güvenlik, minimallik ve standart denetimi (`xai/grok-2` veya `claude-3-7-sonnet`).

`ramazan configure` komutuyla mevcut API anahtarlarınıza göre roller otomatik atanır veya `--architect`, `--worker`, `--reviewer` bayraklarıyla manuel olarak özelleştirilebilir.

### 6.6 Çok Turlu Tool-Calling Döngüsü (Agentic Tool Loop)
Worker agent tek seferlik prompt üreticisi değildir; 15 tura kadar interaktif döngü yürütür:
- `read_file(path, start_line, end_line)`: Kaynak kod ve testleri inceleme.
- `list_dir(path)`: Dizin içeriğini listeleme.
- `write_file(path, content)`: Dosya yazma (Strict scope denetimli).
- `apply_patch(path, diff)`: Unified diff (`@@ ... @@`) ve Search/Replace hunk'larını diskteki dosyalara minimal olarak uygulama.
- `run_command(command)`: Güvenli kabuk komutları çalıştırma.
- `run_tests(path)`: Ara aşamalarda test motorundan anlık geri bildirim alma.
- `git_diff()`: Değişiklikleri yerinde teyit etme.

### 6.7 Katı Hata Semantiği ve Mock Fallback'in Kaldırılması
- Canlı LLM çağrısı başarısız olduğunda (401 Unauthorized, kota aşımı vb.) sistem asla sessiz mock yanıt üretmez.
- `ModelCallError` fırlatılır; geçici hatalar (429, 503) akıllı backoff ile yeniden denenir, kalıcı hatalarda görev `BLOCKED` / `ESCALATED` durumuna çekilerek insan müdahalesi talep edilir.
