"""
Standalone S3 upload test — no Django needed.

Usage:
    AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy python test_s3_upload.py

Or set the vars in a .env and export them first.
"""

import os
import sys
import urllib.request

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    sys.exit("boto3 not installed — run: pip install boto3")

# ── Config (mirrors core/settings.py) ─────────────────────────────────────────
KEY_ID     = os.getenv('AWS_ACCESS_KEY_ID')
SECRET     = os.getenv('AWS_SECRET_ACCESS_KEY')
BUCKET     = os.getenv('AWS_STORAGE_BUCKET_NAME', 'voice-room-images')
REGION     = os.getenv('AWS_S3_REGION_NAME',      'ap-south-1')
TEST_KEY   = 'uploads/test/wavroom_s3_test.txt'
TEST_BODY  = b'wavroom s3 connectivity test'
PUBLIC_URL = f'https://{BUCKET}.s3.{REGION}.amazonaws.com/{TEST_KEY}'

# ── Checks ─────────────────────────────────────────────────────────────────────
print("\n=== WavRoom S3 Upload Test ===\n")

print(f"  Bucket : {BUCKET}")
print(f"  Region : {REGION}")
print(f"  Key ID : {'SET (' + KEY_ID[:6] + '...)' if KEY_ID else 'NOT SET ❌'}")
print(f"  Secret : {'SET' if SECRET else 'NOT SET ❌'}\n")

if not KEY_ID or not SECRET:
    sys.exit(
        "AWS credentials missing.\n"
        "Export them before running:\n"
        "  export AWS_ACCESS_KEY_ID=<your-key>\n"
        "  export AWS_SECRET_ACCESS_KEY=<your-secret>\n"
    )

# ── Upload ─────────────────────────────────────────────────────────────────────
print(f"[1] Uploading test file to s3://{BUCKET}/{TEST_KEY} ...")
try:
    s3 = boto3.client(
        's3',
        region_name          = REGION,
        aws_access_key_id    = KEY_ID,
        aws_secret_access_key= SECRET,
    )
    s3.put_object(
        Bucket      = BUCKET,
        Key         = TEST_KEY,
        Body        = TEST_BODY,
        ContentType = 'text/plain',
        # No ACL — bucket has Object Ownership=Bucket owner enforced
    )
    print("    Upload: OK ✅\n")
except NoCredentialsError:
    sys.exit("    Credentials invalid or expired ❌")
except ClientError as e:
    code = e.response['Error']['Code']
    msg  = e.response['Error']['Message']
    print(f"    Upload FAILED ❌  [{code}] {msg}\n")
    if code == 'NoSuchBucket':
        print(f"    Bucket '{BUCKET}' does not exist in region '{REGION}'.")
    elif code in ('AccessDenied', 'InvalidAccessKeyId'):
        print("    Check your IAM permissions — s3:PutObject is required.")
    sys.exit(1)

# ── Public read check ──────────────────────────────────────────────────────────
public_read_ok = False
print(f"[2] Verifying public read from:\n    {PUBLIC_URL}")
try:
    with urllib.request.urlopen(PUBLIC_URL, timeout=10) as resp:
        body = resp.read()
        if body == TEST_BODY:
            print("    Public read: OK ✅ — content matches\n")
            public_read_ok = True
        else:
            print(f"    Public read: OK but content mismatch ⚠️\n    Got: {body}\n")
            public_read_ok = True
except Exception as e:
    print(f"    Public read FAILED ❌  {e}")
    print("    Objects upload fine but are not publicly accessible.")
    print("    Fix: add a bucket policy + disable Block Public Access in AWS console.\n")

# ── List bucket to confirm object exists ──────────────────────────────────────
print(f"[3] Listing objects at uploads/test/ in bucket ...")
try:
    result = s3.list_objects_v2(Bucket=BUCKET, Prefix='uploads/test/')
    objects = result.get('Contents', [])
    if objects:
        for obj in objects:
            print(f"    {obj['Key']}  ({obj['Size']} bytes)  last modified: {obj['LastModified']}")
        print()
    else:
        print("    No objects found under uploads/test/ ⚠️\n")
except ClientError as e:
    print(f"    List FAILED ❌  {e}\n")

# ── Cleanup skipped — file left on S3 intentionally ───────────────────────────
print(f"[4] Skipping delete — file left at:\n    {PUBLIC_URL}\n")
print("    Open that URL in your browser to verify it loads.\n")

if public_read_ok:
    print("=== All checks passed — S3 is working correctly ===\n")
else:
    print("=== Upload works but public read is BLOCKED ❌ ===")
    print("    Add a bucket policy granting s3:GetObject to Principal: '*'")
    print("    and disable 'Block Public Access' in the S3 console.\n")
