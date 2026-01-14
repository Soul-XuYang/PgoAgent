from datetime import datetime, timedelta, UTC
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import ipaddress
import argparse
import os

def generate_certificate(days_valid:int,cert_dir:str):
    os.makedirs(cert_dir, exist_ok=True)
    # 生成服务器私钥

    private_key = rsa.generate_private_key(
        public_exponent=65537,# 公钥指数
        key_size=2048,
    )


    # 创建证书主题
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"), # 地名随意
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "My organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "my-service.local"),
    ])

    # 使用新的时间API-设置有效时间
    cert = x509.CertificateBuilder().subject_name(
        subject # 主题
    ).issuer_name(
        issuer # 签发人
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(UTC)
    ).not_valid_after(
        datetime.now(UTC) + timedelta(days=days_valid)
    ).add_extension(
        x509.SubjectAlternativeName([
            # 内网域名-本地开发，可依自己需求进行修改替换
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    key_path = os.path.join(cert_dir, "server.key")
    cert_path = os.path.join(cert_dir, "server.crt")
    # 写入并保存私钥
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # 保存证书
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert, private_key

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate SSL certificate')
    parser.add_argument('--days', '-d', type=int, default=365,
                        help='Number of days the certificate should be valid (default: 365)')
    parser.add_argument('--cert_dir', '-c', type=str, default='cert',
                        help='Number of days the certificate should be valid (default: 365)')
    args = parser.parse_args()
    generate_certificate(args.days, args.cert_dir)
    print("GRPC: Certificate and private key have generated successfully.")
