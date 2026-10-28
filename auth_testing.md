# Auth Testing Playbook
1. MongoDB: db.users.findOne({role:"owner"}) -> password_hash starts with $2b$; unique index on users.email.
2. API: curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"...","password":"..."}' ; then curl -b cookies.txt $API/api/auth/me
3. Login returns user + sets httpOnly access_token / refresh_token cookies. 5 failed attempts per ip+email => 15 min lockout (429).
4. No public signup. Users are created by the owner at /api/admin/users.
