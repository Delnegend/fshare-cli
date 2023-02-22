# Fshare CLI

# Features
- [x] Login/logout
- [x] Local cache for session
- [ ] Encrypt local cache
- [x] Select file(s)/folder(s) in working directory to upload while keeping the folder structure
- [x] Locate where to upload
- [x] Upload progress
- [x] Retry when upload failed

# Usage
```bash
$ pip3 install -r requirements.txt
$ python3 fshare.py
```

# Development
- Get an appkey and user-agent at [Fshare](https://www.fshare.vn/api-doc)
- Replace the appkey and user-agent in `fshare.py` line 10 and 11
