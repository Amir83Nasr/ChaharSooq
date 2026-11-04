---
name: Finish and Commit
description: Check remaining work in TODO and git, finish it per AGENTS.md, then commit. Use when asked to finish leftover changes and commit.
---

## Workflow

When this skill runs, do the following in order. Keep responses short and in Persian.

### 1. بررسی وضعیت

1. `git status --short --branch` و `git log --oneline -5` را اجرا کن.
2. `TODO.md` را بخوان — آیتم‌های `[ ]` یعنی کار باقی‌مانده.
3. `git diff HEAD --stat` را ببین — تغییرات کامیت‌نشده فعلی چیست.
4. اگر ابهام بود (کدام آیتم TODO منظور است؟)، قبل از کد زدن با `question` بپرس.

### 2. انجام تغییرات باقی‌مانده

1. فقط کارهای باقی‌مانده واقعی را انجام بده. کد unrelated را ریفکتور نکن.
2. مرزهای `AGENTS.md` را رعایت کن:
   - Backend: `routes → services → repositories → database`. منطق در service، کوئری فقط در repository، تایپ مرزی فقط Pydantic در `app/schemas/`.
   - تغییر اسکیما فقط با Alembic migration در `migrations/` (به‌جز تست/seed).
   - Frontend: UI جنریک در `packages/ui` (بدون منطق بیزینسی و بدون API call)، کامپوزیت اپ در `apps/web/components/`، کامپوننت خصوصی روت در `app/**/_components/`، دیتا-فچینگ بیرون از کامپوننت نمایشی.
   - shadcn/ui اول؛ بدون کتابخانه کامپوننت جدید (بدون ADR).
   - RTL با logical properties؛ فونت فقط `apps/web/app/fonts.ts`؛ قیمت فقط با `<Price />` در `packages/ui`.
   - مقادیر ماشینی (backend/API/DB): عدد لاتین و تومان صحیح. ارقام فارسی، `٬`، `٫`، تاریخ جلالی فقط در UI (`packages/ui/src/lib/`).
   - امنیت: Argon2id، سشن HttpOnly، ریت‌لیمیت لاگین، بدون توکن در localStorage، بدون لاگ/کامیت سکرت.
3. `backend/api/openapi.json` را با دست ویرایش نکن — با اسکریپت تولید می‌شود.
4. `docs/` و `README.md` را همراه تغییر رفتار به‌روز کن.

### 3. اعتبارسنجی قبل از کامیت

به ترتیب اجرا کن و خطا را قبل از کامیت رفع کن:

```bash
make check    # lint + typecheck + tests + db-validate + openapi-check
make build    # production web build
```

- اگر `openapi.json` stale بود، آن را با روش رسمی ریجنریت کن (نه دستی) و دوباره `make openapi-check` بگیر.
- اگر مایگریشن اضافه کردی، `make db-validate` باید سبز باشد.

### 4. کامیت

1. `git status --short` را دوباره ببین. فقط فایل‌های مرتبط را stage کن (`git add <paths>` — نه `git add -A` کور).
2. هرگز کامیت نکن: `.env*`، سکرت، پسورد، توکن، `data/` لوکال. فقط `.env.example`ها مجازند.
3. پیام کامیت به سبک ریپو، انگلیسی کوتاه: `type(scope): subject`
   - typeها: `feat` `fix` `perf` `refactor` `test` `docs` `style` `chore`
   - مثال: `feat(web,api): refresh competitor prices button`
4. هوک‌ها را دور نزن (`--no-verify` ممنوع مگر maintainer بخواهد). Lefthook خودش pre-commit را اجرا می‌کند.
5. بعد از کامیت، `git status --short --branch` و هش کامیت را گزارش بده.

### 5. موارد ممنوع

- پوش (`push`) نکن مگر کاربر صراحتاً بخواهد.
- برنچ عوض نکن یا ریبیس/مرج نکن مگر خواسته شده باشد.
- پوشه workspace یا top-level جدید بدون دلیل مستند (ADR) نساز.
- `latest` در manifest ننویس؛ وابستگی جدید فقط وقتی لازم واقعی باشد.
