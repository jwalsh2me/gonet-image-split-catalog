# gonet-image-split-catalog

Lambda SAM App to Split Source Images in S3 to a TIFF and JPEG Bucket and Catalog EXIF Metadata in DynamoDB

- To deploy in the Adler Account 
  - Do the SAM Build specifying the Adler Template: `sam build -t adler-template.yml`
  - Then you can SAM Deploy, do not specify the template file, but do specify the Env: `sam deploy --config-env adler-prod`

- Normal deployments you can setup your own SAM Env with Var over rides, see `jpw-dev` as an example

