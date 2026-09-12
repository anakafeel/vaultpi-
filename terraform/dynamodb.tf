resource "aws_dynamodb_table" "vaultpi_file_metadata" {
  name         = "VaultPi-FileMetadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true
}
