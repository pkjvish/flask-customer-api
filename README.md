# Flask Customer CRUD API
### Python · Flask · MySQL · Docker · GitHub Actions · AWS ECS Fargate

A production-ready REST API that manages customer records, deployed on AWS ECS
Fargate with a fully automated CI/CD pipeline. The entire AWS infrastructure
is created with a single CloudFormation command — no manual console clicking
for networking, security groups, or IAM roles.

---

## Repository Structure

```
flask-customer-api/
├── app.py                          # Flask routes (GET/POST/PUT/PATCH/DELETE)
├── db.py                           # MySQL connection + schema bootstrap
├── requirements.txt
├── Dockerfile                      # Multi-stage production build
├── docker-compose.yml              # Local dev (Flask + MySQL together)
├── ecs-task-definition.json        # ECS task def template (used by CI/CD)
├── cloudformation.yml              # ONE FILE creates ALL AWS infrastructure
├── .gitignore
├── tests/
│   └── test_app.py                 # Pytest suite (mocked DB)
└── .github/
    └── workflows/
        └── deploy.yml              # GitHub Actions CI/CD pipeline
```

---

## API Reference

Base URL (local): `http://localhost:5000`
Base URL (AWS):   `http://<ALB-DNS-from-CloudFormation-Outputs>`

| Method   | Endpoint                      | Description               |
|----------|-------------------------------|---------------------------|
| `GET`    | `/health`                     | Health + DB status check  |
| `GET`    | `/api/v1/customers`           | List all (paginated)      |
| `POST`   | `/api/v1/customers`           | Create new customer       |
| `GET`    | `/api/v1/customers/<id>`      | Get one customer          |
| `PUT`    | `/api/v1/customers/<id>`      | Full update               |
| `PATCH`  | `/api/v1/customers/<id>`      | Partial update            |
| `DELETE` | `/api/v1/customers/<id>`      | Delete customer           |

### Request / Response Examples

**Create customer**
```bash
curl -X POST http://localhost:5000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Alice",
    "last_name":  "Smith",
    "email":      "alice@example.com",
    "phone":      "+91-98765-43210",
    "city":       "Mumbai",
    "country":    "India"
  }'
```
Response `201`:
```json
{
  "id": 1,
  "first_name": "Alice",
  "last_name": "Smith",
  "email": "alice@example.com",
  "phone": "+91-98765-43210",
  "address": "",
  "city": "Mumbai",
  "country": "India",
  "created_at": "2024-01-01 10:00:00",
  "updated_at": "2024-01-01 10:00:00"
}
```

**List customers (paginated)**
```bash
curl "http://localhost:5000/api/v1/customers?page=1&limit=5"
```

**Partial update**
```bash
curl -X PATCH http://localhost:5000/api/v1/customers/1 \
  -H "Content-Type: application/json" \
  -d '{"city": "Pune"}'
```

**Delete**
```bash
curl -X DELETE http://localhost:5000/api/v1/customers/1
```

---

## PART 1 — Run Locally (5 minutes)

Prerequisites: Docker Desktop installed and running.

```bash
# 1. Clone the repo
git clone https://github.com/<YOUR_USERNAME>/flask-customer-api.git
cd flask-customer-api

# 2. Start Flask API + MySQL together
docker compose up --build

# 3. Test it (new terminal)
curl http://localhost:5000/health
# {"status":"healthy","service":"customer-api","database":"connected"}

curl -X POST http://localhost:5000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Smith","email":"alice@example.com"}'

# 4. Stop everything
docker compose down -v
```

---

## PART 2 — GitHub Repository Setup

### Step 2.1 — Push code to GitHub

```bash
cd flask-customer-api

git init
git add .
git commit -m "feat: flask customer crud api with mysql"

# Create a new EMPTY repo on github.com (no README, no .gitignore)
# Then run:
git remote add origin https://github.com/<YOUR_USERNAME>/flask-customer-api.git
git branch -M main
git push -u origin main
```

### Step 2.2 — Add GitHub Secrets (do this AFTER running CloudFormation in Part 3)

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

You will add these two secrets (values come from CloudFormation Outputs):

| Secret Name              | Where to get the value                              |
|--------------------------|-----------------------------------------------------|
| `AWS_ACCESS_KEY_ID`      | CloudFormation Output: `GitHubActionsAccessKeyId`   |
| `AWS_SECRET_ACCESS_KEY`  | CloudFormation Output: `GitHubActionsSecretAccessKey` |

> ⚠️ The secret access key is shown ONLY ONCE in CloudFormation Outputs.
> Copy it immediately when the stack finishes creating.

### Step 2.3 — Update deploy.yml with your values (do after CloudFormation)

Open `.github/workflows/deploy.yml` and update the `env:` block at the top:

```yaml
env:
  AWS_REGION:     us-east-1                # same region you deployed CloudFormation
  ECR_REPOSITORY: customer-api             # CloudFormation Output: ECRRepositoryName
  ECS_CLUSTER:    customer-api-cluster     # CloudFormation Output: ECSClusterName
  ECS_SERVICE:    customer-api-service     # CloudFormation Output: ECSServiceName
  CONTAINER_NAME: customer-api             # keep as-is (matches ProjectName default)
```

### Step 2.4 — Update ecs-task-definition.json with your values

Open `ecs-task-definition.json` and replace these two placeholders everywhere they appear:

| Placeholder             | Replace with                                    |
|-------------------------|-------------------------------------------------|
| `ACCOUNT_ID_PLACEHOLDER` | CloudFormation Output: `AccountId`             |
| `REGION_PLACEHOLDER`    | CloudFormation Output: `Region` (e.g. us-east-1) |

```bash
# Quick find-replace using sed (Mac/Linux):
# Replace both placeholders (run from project root):
sed -i 's/ACCOUNT_ID_PLACEHOLDER/123456789012/g' ecs-task-definition.json
sed -i 's/REGION_PLACEHOLDER/us-east-1/g' ecs-task-definition.json
```

Then commit and push:
```bash
git add .github/workflows/deploy.yml ecs-task-definition.json
git commit -m "config: add AWS account and region values"
git push origin main
```

---

## PART 3 — AWS Setup (Everything via CloudFormation)

### What does cloudformation.yml create?

Running ONE command creates ALL of this automatically:

```
VPC (10.0.0.0/16)
├── Public Subnet 1 (10.0.1.0/24) — AZ-a  ← ALB + ECS tasks
├── Public Subnet 2 (10.0.2.0/24) — AZ-b  ← ALB + ECS tasks
├── Private Subnet 1 (10.0.3.0/24) — AZ-a ← RDS MySQL
├── Private Subnet 2 (10.0.4.0/24) — AZ-b ← RDS MySQL
├── Internet Gateway + Route Tables
├── Security Groups:
│   ├── ALB SG       (port 80 from internet → ALB)
│   ├── ECS SG       (port 5000 from ALB → ECS tasks only)
│   └── RDS SG       (port 3306 from ECS tasks only)
├── Application Load Balancer (public, port 80)
├── ECR Repository (Docker images)
├── RDS MySQL 8 db.t3.micro (private, free-tier)
├── ECS Fargate Cluster
├── ECS Task Definition (256 CPU, 512 MB)
├── ECS Service (1 task)
├── CloudWatch Log Group (/ecs/customer-api, 30 days)
├── IAM: ECSTaskExecutionRole (ECR pull + CloudWatch + SSM)
├── IAM: ECSTaskRole (for your app code)
├── IAM: GitHubActionsUser + AccessKey (least-privilege CI/CD)
└── SSM Parameter Store: DB_HOST, DB_USER, DB_PASSWORD
```

---

### Step 3.1 — Install AWS CLI

```bash
# macOS
brew install awscli

# Windows (run in PowerShell as Administrator)
winget install Amazon.AWSCLI

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify
aws --version
```

### Step 3.2 — Create an IAM user for your local AWS CLI

You need temporary credentials to run the CloudFormation deployment.
After the stack is created, GitHub Actions uses a different user (auto-created by CloudFormation).

1. Sign in to **AWS Console** at https://console.aws.amazon.com
2. Go to **IAM → Users → Create user**
3. Username: `cloudformation-admin`
4. Click **Next**
5. Select **"Attach policies directly"**
6. Search and attach: **`AdministratorAccess`**
   (this is safe for initial setup; you can restrict it later)
7. Click **Create user**
8. Click the user → **Security credentials** tab
9. Click **Create access key**
10. Select **"Command Line Interface (CLI)"** → Next
11. Click **Create access key**
12. **COPY BOTH VALUES** — you will not see the secret again

### Step 3.3 — Configure AWS CLI

```bash
aws configure
```

Enter the values when prompted:
```
AWS Access Key ID:     paste your cloudformation-admin key ID
AWS Secret Access Key: paste your cloudformation-admin secret key
Default region name:   us-east-1         ← choose your preferred region
Default output format: json
```

Verify it works:
```bash
aws sts get-caller-identity
# Should show your account ID and user ARN
```

### Step 3.4 — Deploy CloudFormation Stack

This single command creates ALL the infrastructure (~10-15 minutes for RDS):

```bash
aws cloudformation create-stack \
  --stack-name customer-api-stack \
  --template-body file://cloudformation.yml \
  --parameters \
      ParameterKey=DBPassword,ParameterValue=MySecurePassword123! \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

> Replace `MySecurePassword123!` with your own strong password (min 8 chars).
> You can also change the region from `us-east-1` to your preferred region.

**Watch the stack creation progress:**
```bash
# Option A: Check status from CLI every 30 seconds
watch -n 30 "aws cloudformation describe-stacks \
  --stack-name customer-api-stack \
  --query 'Stacks[0].StackStatus' \
  --output text"

# Option B: Watch in the Console
# AWS Console → CloudFormation → Stacks → customer-api-stack → Events tab
```

Stack status will go through:
`CREATE_IN_PROGRESS` → (wait ~10-15 min for RDS) → `CREATE_COMPLETE`

### Step 3.5 — Get the Output Values

Once the stack shows `CREATE_COMPLETE`:

```bash
aws cloudformation describe-stacks \
  --stack-name customer-api-stack \
  --query "Stacks[0].Outputs" \
  --output table
```

You will see a table like this:
```
OutputKey                      | OutputValue
-------------------------------|--------------------------------------------------
GitHubActionsAccessKeyId       | AKIA...
GitHubActionsSecretAccessKey   | wJalrX...  ← COPY THIS NOW, shown only once
ECSClusterName                 | customer-api-cluster
ECSServiceName                 | customer-api-service
ECRRepositoryName              | customer-api
ECRRepositoryURI               | 123456789012.dkr.ecr.us-east-1.amazonaws.com/customer-api
AWSRegion                      | us-east-1
AccountId                      | 123456789012
Region                         | us-east-1
LoadBalancerURL                | http://customer-api-alb-123456789.us-east-1.elb.amazonaws.com
RDSEndpoint                    | customer-api-mysql.xxxxx.us-east-1.rds.amazonaws.com
```

### Step 3.6 — Complete the GitHub setup using Outputs

Now go back to Part 2 Steps 2.2, 2.3, 2.4 and fill in these values.

---

## PART 4 — Trigger First Deployment

After completing Parts 2 and 3:

```bash
# Any push to main triggers the full pipeline
git add .
git commit -m "config: set aws account and region"
git push origin main
```

**Watch the pipeline:**
1. GitHub repo → **Actions** tab → Click the running workflow
2. You will see two jobs: `Run Unit Tests` → `Build → Push to ECR → Deploy to ECS`
3. The deploy job waits until the ECS task is actually healthy (can take ~3 min)

**Pipeline flow:**
```
git push main
    │
    ▼
Job 1: Unit Tests (pytest)
    │  pass
    ▼
Job 2: Build & Deploy
    ├── docker build (multi-stage)
    ├── docker push → ECR  (tagged with git SHA + latest)
    ├── render new ECS task definition (inject real image URI)
    └── aws ecs update-service → new Fargate task starts → old task drains
```

---

## PART 5 — Verify the Deployment

```bash
# Get your ALB URL from CloudFormation Outputs or:
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name customer-api-stack \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
  --output text)

echo "API URL: $ALB_URL"

# Health check
curl $ALB_URL/health

# Create a customer
curl -X POST $ALB_URL/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Smith","email":"alice@example.com","city":"Mumbai","country":"India"}'

# List customers
curl $ALB_URL/api/v1/customers

# Get one customer
curl $ALB_URL/api/v1/customers/1

# Update city only
curl -X PATCH $ALB_URL/api/v1/customers/1 \
  -H "Content-Type: application/json" \
  -d '{"city":"Delhi"}'

# Delete
curl -X DELETE $ALB_URL/api/v1/customers/1
```

---

## PART 6 — Troubleshooting

| Problem | Where to look | Fix |
|---------|---------------|-----|
| CloudFormation stuck | Console → CloudFormation → Events tab | Read the error event at the bottom |
| ECS task keeps stopping | Console → ECS → cluster → Tasks → Stopped tasks → Logs | Usually a DB connection error |
| DB connection refused | CloudWatch Logs `/ecs/customer-api` | Check SSM params have correct RDS endpoint |
| GitHub Actions: ECR push denied | Actions log | Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets are set |
| GitHub Actions: ECS service not found | Actions log | Check `ECS_CLUSTER` and `ECS_SERVICE` in deploy.yml match CloudFormation Outputs |
| `ecs-task-definition.json` error | Actions log | Make sure both placeholders are replaced with real account ID and region |
| curl returns 502 Bad Gateway | Browser/curl | ECS task is still starting — wait 2 min and try again |

**View ECS task logs:**
```bash
aws logs tail /ecs/customer-api --follow
```

**Restart ECS service (force new deployment):**
```bash
aws ecs update-service \
  --cluster customer-api-cluster \
  --service customer-api-service \
  --force-new-deployment
```

---

## PART 7 — Teardown (avoid AWS charges)

```bash
# Delete the CloudFormation stack (removes ALL resources)
# Note: RDS takes a final snapshot first (DeletionPolicy: Snapshot)
aws cloudformation delete-stack \
  --stack-name customer-api-stack \
  --region us-east-1

# Watch deletion progress
aws cloudformation describe-stacks \
  --stack-name customer-api-stack \
  --query "Stacks[0].StackStatus" \
  --output text
# When done: "Stack with id ... does not exist"
```
