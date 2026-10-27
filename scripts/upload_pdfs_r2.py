# -*- coding: utf-8 -*-
"""把课程 PDF 上传到 Cloudflare R2，并生成 data/pdf_manifest.json。

清单会入库，后端据此知道哪些文献有 PDF、对象键是什么。PDF 本身不上传仓库。

需要环境变量，写在项目根目录 .env 或直接设进环境：
    R2_ACCOUNT_ID
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_BUCKET

可选：
    R2_KEY_PREFIX    对象键前缀，默认 papers
    PDF_BASE_URL     R2 公开访问地址，如 https://pub-xxxx.r2.dev，仅用于打印核对

用法：
    python scripts/upload_pdfs_r2.py --dry-run
    python scripts/upload_pdfs_r2.py
"""
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANIFEST = DATA / "pdf_manifest.json"
LOCAL_BASE = ROOT / "2020-2025年专业文献及政策案例作业"
LEGACY_BASE = ROOT.parent / "2020-2025年专业文献及政策案例作业"


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    dry = "--dry-run" in sys.argv

    account = os.environ.get("R2_ACCOUNT_ID", "").strip()
    bucket = os.environ.get("R2_BUCKET", "").strip()
    key_id = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    prefix = os.environ.get("R2_KEY_PREFIX", "papers").strip("/")
    base = LOCAL_BASE if LOCAL_BASE.exists() else LEGACY_BASE

    missing_env = [k for k, v in {
        "R2_ACCOUNT_ID": account, "R2_BUCKET": bucket,
        "R2_ACCESS_KEY_ID": key_id, "R2_SECRET_ACCESS_KEY": secret,
    }.items() if not v]
    if missing_env and not dry:
        print("缺少环境变量：" + "、".join(missing_env))
        return 1

    papers = json.loads((DATA / "papers.json").read_text(encoding="utf-8"))
    s3 = None if dry else boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )

    manifest, uploaded, skipped, total = {}, 0, 0, 0
    for i, p in enumerate(papers, 1):
        rel = p.get("path") or ""
        src = base / rel
        if not rel or not src.is_file():
            skipped += 1
            continue
        key = f"{prefix}/{p['cat']}.pdf"
        size = src.stat().st_size
        total += size
        if dry:
            print(f"  {p['cat']}  {size/1024/1024:5.1f} MB  -> {key}")
        else:
            s3.upload_file(
                str(src), bucket, key,
                ExtraArgs={"ContentType": "application/pdf",
                           "CacheControl": "public, max-age=86400"},
            )
            print(f"  [{i}/{len(papers)}] {p['cat']}  {size/1024/1024:.1f} MB")
        manifest[p["cat"]] = {"key": key, "bytes": size}
        uploaded += 1

    if dry:
        print(f"\n试运行：可上传 {uploaded} 篇，缺失 {skipped} 篇，合计 {total/1024/1024:.1f} MB")
        print("确认无误后去掉 --dry-run 真正上传。")
        return 0

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已上传 {uploaded} 篇，跳过 {skipped} 篇，合计 {total/1024/1024:.1f} MB")
    print(f"清单写入 {MANIFEST}")
    print("接下来：把公开访问地址填进服务的 PDF_BASE_URL，提交清单，重新部署。")


if __name__ == "__main__":
    sys.exit(main())
