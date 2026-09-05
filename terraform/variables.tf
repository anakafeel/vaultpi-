variable "aws_region" {
  description = "AWS region all VaultPi resources live in"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account ID that owns these resources"
  type        = string
  default     = "527557824370"
}

variable "s3_bucket_name" {
  description = "Name of the existing VaultPi S3 bucket"
  type        = string
  default     = "saim-vaultpi-files"
}
