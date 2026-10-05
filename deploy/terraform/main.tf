# ============================================================
# main.tf — FleetGuard AWS EC2 Infrastructure
#
# Provisions:
#   - VPC with public subnet
#   - Security group (ports 22, 80, 9090, 3000)
#   - EC2 t3.medium instance with Docker + Docker Compose
#   - Elastic IP (static public IP)
#   - S3 bucket for raw telemetry archive
#
# Usage:
#   terraform init
#   terraform plan -var="key_pair_name=your-key"
#   terraform apply -var="key_pair_name=your-key"
# ============================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "key_pair_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"   # 2 vCPU, 4GB RAM — enough for full stack
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
  default     = "fleetguard_prod_secret"
}

variable "grafana_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "fleetguard_grafana"
}

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Networking ────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "fleetguard-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "fleetguard-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"
  tags = { Name = "fleetguard-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "fleetguard-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "fleetguard" {
  name        = "fleetguard-sg"
  description = "FleetGuard application security group"
  vpc_id      = aws_vpc.main.id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

  # HTTP (nginx → React + API)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  # Prometheus UI (optional — restrict in production)
  ingress {
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Prometheus"
  }

  # Grafana direct access (also available at /grafana via nginx)
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Grafana"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "fleetguard-sg" }
}

# ── S3 bucket (raw telemetry archive) ────────────────────────────────────────

resource "aws_s3_bucket" "telemetry" {
  bucket = "fleetguard-telemetry-${random_id.suffix.hex}"
  tags   = { Name = "fleetguard-telemetry", Project = "FleetGuard" }
}

resource "aws_s3_bucket_versioning" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "telemetry" {
  bucket = aws_s3_bucket.telemetry.id
  rule {
    id     = "archive-old-telemetry"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    filter { prefix = "telemetry/" }
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

# ── IAM role for EC2 (S3 access) ─────────────────────────────────────────────

resource "aws_iam_role" "ec2_role" {
  name = "fleetguard-ec2-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "fleetguard-s3-access"
  role = aws_iam_role.ec2_role.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.telemetry.arn,
        "${aws_s3_bucket.telemetry.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "fleetguard-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────

resource "aws_instance" "fleetguard" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.fleetguard.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    postgres_password = var.postgres_password
    grafana_password  = var.grafana_password
    s3_bucket         = aws_s3_bucket.telemetry.bucket
    aws_region        = var.aws_region
  })

  tags = {
    Name    = "fleetguard-server"
    Project = "FleetGuard"
  }
}

# ── Elastic IP ────────────────────────────────────────────────────────────────

resource "aws_eip" "fleetguard" {
  instance = aws_instance.fleetguard.id
  domain   = "vpc"
  tags     = { Name = "fleetguard-eip" }
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "public_ip" {
  description = "FleetGuard public IP address"
  value       = aws_eip.fleetguard.public_ip
}

output "public_url" {
  description = "FleetGuard application URL"
  value       = "http://${aws_eip.fleetguard.public_ip}"
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = "http://${aws_eip.fleetguard.public_ip}/grafana"
}

output "api_docs_url" {
  description = "FastAPI documentation"
  value       = "http://${aws_eip.fleetguard.public_ip}/api/docs"
}

output "s3_bucket" {
  description = "S3 telemetry archive bucket"
  value       = aws_s3_bucket.telemetry.bucket
}

output "ssh_command" {
  description = "SSH into the server"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.fleetguard.public_ip}"
}
