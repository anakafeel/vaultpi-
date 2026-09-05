resource "aws_s3_bucket" "vaultpi_files" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_public_access_block" "vaultpi_files" {
  bucket = aws_s3_bucket.vaultpi_files.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vaultpi_files" {
  bucket = aws_s3_bucket.vaultpi_files.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "vaultpi_files" {
  bucket = aws_s3_bucket.vaultpi_files.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_notification" "vaultpi_files" {
  bucket = aws_s3_bucket.vaultpi_files.id

  lambda_function {
    id                  = "428225e6-2765-4ca5-bd83-7274ce242ed4"
    lambda_function_arn = aws_lambda_function.vaultpi_process_upload.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "photos/"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}
