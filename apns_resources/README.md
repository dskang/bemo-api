## Files

- Bemo.certSigningRequest: CSR used for creating Development Push SSL Certificate
- bemo_key.p12: Exported version of Bemo private key
- bemo_dev_ssl_cert.cer: SSL certificate for Bemo Development Push
- bemo_prod_ssl_cert.cer: SSL certificate for Bemo Production Push

## Creating PEM files

    openssl x509 -in cert.cer -inform DER -outform PEM -out cert.pem
    openssl pkcs12 -in key.p12 -out key.pem -nodes
