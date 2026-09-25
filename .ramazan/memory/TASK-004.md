# Task Memory: TASK-004

## Title
Zıplayan Maymun Mobil Oyunu (Single-File HTML & JS)

## Completed
Zıplayan Maymun oyunu tek dosya HTML/JS olarak kodlandı ve mobil viewport ile dokunmatik kontroller doğrulandı.

## Files Changed
- `monkey_game.html`
- `tests/test_monkey_game.py`

## Important Decisions
- Canvas 2D context ile saf JavaScript fizik motoru ve dokunmatik D-Pad kontrolleri kullanıldı.
- Sıfır harici bağımlılık ile tek dosya HTML/JS olarak mimarilendirildi.

## Problems Encountered
- İlk oluşturmada task JSON dosyası kaydedilmeden commit edilmiş, TASK-005 üretildiğinde ID sırası atlanarak state tutarsızlığına yol açmıştı.

## Resolution
- TASK-004 deterministik olarak TaskStore ve Memory altına kaydedildi, state recompute edilerek senkronize edildi.

## Tests
- `tests/test_monkey_game.py` başarıyla geçti (100% assertions).
