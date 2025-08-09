from django.test import Client

c = Client()
res1 = c.get("/")  # Expect redirect to /anti_ddos/challenge/
res2 = c.get("/anti_ddos/challenge/")  # Expect 200 OK
res3 = c.post("/anti_ddos/challenge/", {"next": "/"})
print(
    "res1 status:", res1.status_code, "redirect:", getattr(res1, "url", "No redirect")
)
print("res2 status:", res2.status_code)
print("res3 status:", res3.status_code)
print("ddos_passed flag:", c.session.get("ddos_passed"))
