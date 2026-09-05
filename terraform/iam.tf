### Lambda execution role ###

resource "aws_iam_role" "vaultpi_lambda_role" {
  name = "VaultPi-Lambda-Role"

  description = "Allows Lambda functions to call AWS services on your behalf."

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# NOTE: the console has AmazonDynamoDBFullAccess AND AmazonDynamoDBFullAccess_v2
# both attached simultaneously - a real discrepancy found during import, not
# something intentionally configured this way. Left as-is to match reality;
# not applying a fix here since that would modify a live, in-use role.
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "s3_read_only" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "dynamodb_full_access" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "dynamodb_full_access_v2" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
}

resource "aws_iam_role_policy_attachment" "rekognition_full_access" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonRekognitionFullAccess"
}

resource "aws_iam_role_policy_attachment" "bedrock_full_access" {
  role       = aws_iam_role.vaultpi_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

### Grafana CloudWatch read-only user (Milestone 6) ###

resource "aws_iam_user" "vaultpi_grafana_cloudwatch" {
  name = "vaultpi-grafana-cloudwatch"
}

resource "aws_iam_policy" "vaultpi_grafana_cloudwatch_readonly" {
  name = "VaultPiGrafanaCloudWatchReadOnly"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchMetricsReadOnly"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:DescribeAlarmsForMetric",
          "cloudwatch:DescribeAlarms",
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "grafana_cloudwatch_readonly" {
  user       = aws_iam_user.vaultpi_grafana_cloudwatch.name
  policy_arn = aws_iam_policy.vaultpi_grafana_cloudwatch_readonly.arn
}

# The access key itself is intentionally NOT managed here - AWS never
# returns a secret access key after creation, so importing it would leave
# Terraform state with an unknown/unusable secret. The key already exists
# and is in use by Grafana's .env file; it's tracked outside Terraform.
