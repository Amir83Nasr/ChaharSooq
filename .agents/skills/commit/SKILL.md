---
name: commit
description: Finish the requested work per AGENTS.md and commit only the changes this run made. Use when asked to commit, finish leftover changes and commit, or commit all changes (explicitly). Never pushes unless asked.
---

# Commit

Keep responses short and in Persian.

## قاعده اصلی: فقط تغییرات خودت را کامیت کن

در این اجرا فقط فایل‌هایی را کامیت کن که **خودت** در همین اجرا ساخته یا تغییر داده‌ای. تغییرات کامیت‌نشده‌ی قبلیِ کاربر مال اوست: نه stage کن، نه stash کن، نه revert کن.

- از ابتدای اجرا لیست فایل‌های لمس‌شده را نگه دار: هر `write`/`edit`، هر فایل تولیدشده (مثل `openapi.json` بعد از ریجنریت)، و هر فایلی که فرمتر/لیتر/کدجن عوض کرده.
- موقع کامیت همان لیست را **مسیر به مسیر** stage کن. `git add -A`، `git add .` و `git commit -a` ممنوع.
- قبل از اولین ویرایش، `git status --short` را بگیر تا بدانی چه چیزی از قبل dirty بوده. در پایان، فایل‌های dirty خارج از لیستت را دست نزن و در گزارش با برچسب «کامیت نشد» بیاور.
- اگر یک فایل هم تغییر قبلی کاربر را دارد و هم تغییر تو:
  - با `git diff <path>` بررسی کن.
  - اگر هانک‌ها جدا هستند، با `git add -p` فقط هانک‌های خودت را stage کن.
  - اگر جدا کردن امن نیست، قبل از ادامه با `question` بپرس.
- استثنای واحد: کاربر صریح گفته باشد «همه تغییرات را کامیت کن / all changes». تنها در این حالت همه‌ی تغییرات را (بعد از بازبینی `git diff`) stage کن؛ قواعد ممنوعیتِ سکرت و `data/` هنوز برقرارند.

## TODO.md مال کاربر است

- `TODO.md` را نخوان، ویرایش نکن، به‌روز نکن و کامیت نکن. کاربر خودش دستی مدیریتش می‌کند.
- اگر `TODO.md` dirty بود، جزو تغییرات کاربر حساب می‌شود و حتی با «همه تغییرات را کامیت کن» هم stage نمی‌شود.
- برای فهم کارِ خواسته‌شده فقط از پیام کاربر استفاده کن؛ اگر مبهم بود بپرس، از TODO حدس نزن.

## Workflow

### 1. بررسی وضعیت

1. `git status --short --branch` و `git log --oneline -5` را اجرا کن.
2. `git diff HEAD --stat` را ببین — تغییرات کامیت‌نشده فعلی چیست و چه چیزی از قبل وجود داشته.
3. اگر کار درخواستی مبهم بود، قبل از کد زدن با `question` بپرس.

### 2. انجام کار درخواستی

1. فقط همان کاری را انجام بده که خواسته شده؛ کار باقی‌ماندهٔ حدسی از TODO یا کد unrelated را اضافه نکن و ریفکتور نکن.
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

1. `git status --short` را دوباره ببین و لیست فایل‌های خودت را نهایی کن (طبق قاعده اصلی بالا).
2. فقط همان فایل‌ها را stage کن: `git add <path> ...`.
3. `git diff --cached --stat` و در صورت نیاز `git diff --cached` را ببین تا مطمئن شوی فقط کار خودت داخل است.
4. هرگز کامیت نکن: `.env*`، سکرت، پسورد، توکن، `data/` لوکال، `TODO.md`. فقط `.env.example`ها مجازند.
5. پیام کامیت به سبک ریپو، انگلیسی کوتاه: `type(scope): subject`
   - typeها: `feat` `fix` `perf` `refactor` `test` `docs` `style` `chore`
   - مثال: `feat(web,api): refresh competitor prices button`
6. هوک‌ها را دور نزن (`--no-verify` ممنوع مگر maintainer بخواهد). Lefthook خودش pre-commit را اجرا می‌کند. اگر هوک شکست، مشکل را رفع کن نه اینکه دورش بزنی.
7. `commit --amend`، `rebase` و `reset` روی کامیت‌های قبلی ممنوع است مگر صریح خواسته شود.

### 5. گزارش پایانی

1. هش کامیت و پیام آن را بده.
2. فایل‌های داخل کامیت را فهرست کن.
3. تغییرات dirty که کامیت نشدند (چون مال کاربر یا نامرتبط بودند) را جدا لیست کن.
4. وضعیت `git status --short --branch` و اختلاف با remote را بگو (بدون پوش).

## پوش

- پیش‌فرض: **پوش نکن.** فقط وقتی کاربر صریح گفته «پوش کن / push»، `git push` روی برنچ فعلی بزن.
- `--force` (و `--force-with-lease`) فقط با درخواست صریح.
- بعد از پوش، برنچ و remote و نتیجه را گزارش کن.

## موارد ممنوع

- پوش بدون درخواست صریح.
- خواندن، ویرایش یا کامیت کردن `TODO.md` (مدیریتش دستی با کاربر است).
- stage کردن تغییرات قبلی کاربر یا فایل‌های نامرتبط به بهانه‌ی «همه با هم».
- برنچ عوض کردن، ریبیس یا مرج بدون درخواست.
- ساخت پوشه workspace یا top-level جدید بدون دلیل مستند (ADR).
- نوشتن `latest` در manifest؛ وابستگی جدید فقط وقتی لازم واقعی باشد.
