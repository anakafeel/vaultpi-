# The Lambda's code was deployed by pasting directly into the console, not
# via a Terraform-managed artifact. This zip is only here so the resource
# has a valid `filename`/`source_code_hash` argument to import against;
# actual code changes should keep being deployed however they are today
# until a real CI/CD pipeline replaces that. Changes to it are intentionally
# ignored below so `terraform plan` never tries to redeploy code.
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/process_upload/lambda_function.py"
  output_path = "${path.module}/lambda_function_payload.zip"
}

resource "aws_lambda_function" "vaultpi_process_upload" {
  function_name = "VaultPi-ProcessUpload"
  role          = aws_iam_role.vaultpi_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.14"
  timeout       = 30
  memory_size   = 256
  architectures = ["x86_64"]
  package_type  = "Zip"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "lambda-f804cd56-f29c-4646-93fb-22dc71c26fb5"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.vaultpi_process_upload.function_name
  principal     = "s3.amazonaws.com"
  source_account = var.aws_account_id
  source_arn    = aws_s3_bucket.vaultpi_files.arn
}
