feat(anti-ddos): alias /anti_ddos/challenge to captcha; SVG+fallback; headers; plus perf/caching/monitoring

Summary
- /anti_ddos/challenge/ now redirects to /anti_ddos/captcha/ so both endpoints present the same CAPTCHA.
- anti_ddos/captcha.html renders the math as inline SVG with a plaintext fallback for theme immunity.
- GET responses include Cache-Control: no-store and X-AntiDDoS-Trace headers.
- Wrong answer re-renders with error; correct answer sets antiddos_ok and redirects to /.
- Middleware and OpenResty gatekeeper allow both paths; root (/) redirect points to /anti_ddos/captcha/.
- Includes previous perf/caching improvements on list/admin templates and PerfMonitorMiddleware for light monitoring/log reduction.

Verification (via Tor)
- /anti_ddos/captcha/?nocache=1:
  - 200 OK; headers: Cache-Control: no-store, X-AntiDDoS-Trace: <hex>
  - Contains inline SVG of math and a plaintext fallback element (#challenge-fallback)
- /anti_ddos/challenge/?nocache=1:
  - 302 Found → /anti_ddos/captcha/
  - Following redirect shows same math SVG + fallback
- manage.py check returns no issues.
- Public lists (/products/, /vendors/, /disputes/) do not emit Set-Cookie for anonymous users.

Key Files Changed
- apps/anti_ddos/views.py: challenge view redirects to captcha; captcha view sets headers and robustly generates challenge_text and answer; logs verification.
- apps/anti_ddos/templates/anti_ddos/captcha.html: inline SVG rendering with plaintext fallback and trace comment.
- core/templatetags/svg_extras.py: render_math_svg with high-contrast fill and aria-label.
- openresty/nginx.conf: root (/) redirect updated to /anti_ddos/captcha/.
- marketplace/settings.py: TTL tuned, CSRF trusted origins include onion, perf middleware enabled.
- core/middleware/perf_monitor.py: lightweight request logging.
- Multiple ORM hot-path and fragment caching changes (admin/public lists), respecting safety rules for authenticated pages/CSRF-bearing forms.

Link to Devin run
https://app.devin.ai/sessions/b2bd7fcec7014f328e01d86485b6c326

Requester
Cosmetic (@Joshluxr)
