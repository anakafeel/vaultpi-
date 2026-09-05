output "s3_bucket_name" {
  description = "Name of the VaultPi S3 bucket"
  value       = aws_s3_bucket.vaultpi_files.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the VaultPi S3 bucket"
  value       = aws_s3_bucket.vaultpi_files.arn
}

output "lambda_function_arn" {
  description = "ARN of the VaultPi-ProcessUpload Lambda function"
  value       = aws_lambda_function.vaultpi_process_upload.arn
}

output "lambda_function_name" {
  description = "Name of the VaultPi-ProcessUpload Lambda function"
  value       = aws_lambda_function.vaultpi_process_upload.function_name
}

output "dynamodb_table_name" {
  description = "Name of the VaultPi-FileMetadata DynamoDB table"
  value       = aws_dynamodb_table.vaultpi_file_metadata.name
}

output "dynamodb_table_arn" {
  description = "ARN of the VaultPi-FileMetadata DynamoDB table"
  value       = aws_dynamodb_table.vaultpi_file_metadata.arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.vaultpi_lambda_role.arn
}

output "grafana_cloudwatch_user_arn" {
  description = "ARN of the IAM user Grafana uses for CloudWatch read access"
  value       = aws_iam_user.vaultpi_grafana_cloudwatch.arn
}
