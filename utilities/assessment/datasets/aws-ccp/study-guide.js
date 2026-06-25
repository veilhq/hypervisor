// ===================================================================
// CLF-C02 Study Guide — Complete domain reference material
// ===================================================================
// Covers all in-scope topics per the official AWS CLF-C02 exam guide.
// Edit this file to add/update study material without touching the engine.
// ===================================================================

// Generic name for the assessment engine (aliased from CCP_STUDY_GUIDE for backward compat)
window.QUIZ_STUDY_GUIDE = [
  {
    domain: 1,
    title: "Cloud Concepts",
    weight: "24% of exam (~16 questions)",
    sections: [
      {
        heading: "Six Advantages of Cloud Computing",
        points: [
          "Trade fixed expense for variable expense — pay only for what you consume",
          "Benefit from massive economies of scale — AWS aggregates usage across customers for lower prices",
          "Stop guessing capacity — scale up or down based on actual demand",
          "Increase speed and agility — provision resources in minutes, not weeks",
          "Stop spending money running and maintaining data centers",
          "Go global in minutes — deploy to multiple Regions worldwide"
        ]
      },
      {
        heading: "Cloud Deployment Models",
        points: [
          "Public cloud — everything runs on the cloud provider (AWS, Azure, GCP)",
          "Private cloud (on-premises) — resources deployed in your own data center using cloud-like tech",
          "Hybrid cloud — connects on-premises infrastructure to cloud resources"
        ]
      },
      {
        heading: "Cloud Service Models",
        points: [
          "IaaS (Infrastructure as a Service) — most control: networking, storage, compute (e.g. EC2)",
          "PaaS (Platform as a Service) — managed platform, you manage code and data (e.g. Elastic Beanstalk)",
          "SaaS (Software as a Service) — fully managed application (e.g. Gmail, Salesforce)"
        ]
      },
      {
        heading: "Well-Architected Framework (6 Pillars)",
        points: [
          "Operational Excellence — run and monitor systems, continually improve",
          "Security — protect information, systems, and assets",
          "Reliability — recover from failures, meet demand",
          "Performance Efficiency — use resources efficiently as demand changes",
          "Cost Optimization — avoid unnecessary costs",
          "Sustainability — minimize environmental impact"
        ]
      },
      {
        heading: "Key Concepts",
        points: [
          "Elasticity — automatically scale resources up/down to match demand",
          "High availability — design for minimal downtime using redundancy (multiple AZs)",
          "Fault tolerance — system continues operating when a component fails",
          "Regions — geographically isolated areas (e.g. us-east-1, eu-west-1)",
          "Availability Zones (AZs) — isolated data centers within a Region",
          "Edge locations — CDN endpoints for caching content closer to users",
          "AWS Local Zones — extend a Region closer to end users for low-latency apps",
          "AWS Wavelength Zones — ultra-low latency at 5G network edges",
          "AWS Outposts — run AWS infrastructure on-premises for hybrid workloads"
        ]
      },
      {
        heading: "Migration Strategies & Cloud Adoption",
        points: [
          "AWS Cloud Adoption Framework (CAF) — guidance across 6 perspectives: Business, People, Governance, Platform, Security, Operations",
          "7 Rs of Migration — Rehost (lift and shift), Replatform (lift, tinker, shift), Refactor (re-architect), Repurchase (drop and shop), Retain, Retire, Relocate",
          "AWS Migration Hub — central place to track migrations across AWS tools",
          "AWS Application Migration Service — automates lift-and-shift migrations",
          "AWS Snowball / Snowball Edge — physical devices for large-scale data transfer",
          "AWS Database Migration Service (DMS) — migrate databases to AWS with minimal downtime",
          "AWS Schema Conversion Tool (SCT) — convert database schemas between engines"
        ]
      },
      {
        heading: "Cloud Economics",
        points: [
          "Fixed costs vs. variable costs — cloud converts CapEx to OpEx",
          "Rightsizing — match instance types to actual workload needs to avoid waste",
          "Licensing — BYOL (Bring Your Own License) vs. license-included options",
          "Automation benefits — AWS CloudFormation for repeatable provisioning",
          "Managed services reduce operational overhead — RDS, ECS, EKS, DynamoDB"
        ]
      }
    ]
  },
  {
    domain: 2,
    title: "Security & Compliance",
    weight: "30% of exam (~20 questions)",
    sections: [
      {
        heading: "Shared Responsibility Model",
        points: [
          "AWS responsibility: security OF the cloud — hardware, software, networking, facilities",
          "Customer responsibility: security IN the cloud — data, configuration, access management, encryption",
          "AWS manages: physical security, hypervisor patching, global infrastructure, managed service internals",
          "Customer manages: OS patching (on EC2), firewall/security group rules, IAM policies, data encryption, application code",
          "Responsibility shifts by service — e.g. RDS: AWS patches the DB engine; Lambda: AWS manages everything except your code"
        ]
      },
      {
        heading: "Identity and Access Management (IAM)",
        points: [
          "Users — individual identities with long-term credentials",
          "Groups — collections of users sharing the same permissions",
          "Roles — temporary credentials for services or cross-account access (preferred over access keys)",
          "Policies — JSON documents defining allow/deny permissions",
          "Principle of least privilege — grant only the minimum permissions needed",
          "MFA (Multi-Factor Authentication) — adds a second verification factor beyond password",
          "Root account — has full access; secure it with MFA, avoid using for daily tasks",
          "IAM Identity Center (SSO) — centralized single sign-on for multiple AWS accounts and apps",
          "AWS Secrets Manager — rotate, manage, and retrieve database credentials and API keys",
          "Federated identity — use external identity providers (SAML, OIDC) for AWS access"
        ]
      },
      {
        heading: "Security Services",
        points: [
          "AWS Shield — managed DDoS protection (Standard is free, Advanced is paid)",
          "AWS WAF — web application firewall; blocks SQL injection, XSS, and other web exploits",
          "Amazon GuardDuty — continuous threat detection using ML and threat intelligence",
          "Amazon Inspector — automated vulnerability assessments for EC2 and containers",
          "Amazon Macie — discovers and protects sensitive data (PII) in S3 using ML",
          "AWS KMS — create and manage encryption keys for data at rest and in transit",
          "AWS Certificate Manager — provision and manage SSL/TLS certificates",
          "AWS Security Hub — aggregates security findings from GuardDuty, Inspector, Macie, and more",
          "Amazon Detective — investigate and analyze security findings with visualizations",
          "AWS Firewall Manager — centrally manage firewall rules across accounts"
        ]
      },
      {
        heading: "Auditing and Compliance",
        points: [
          "AWS CloudTrail — records all API calls on your account (who, what, when, where)",
          "AWS Config — continuously evaluates resource configurations against rules",
          "AWS Audit Manager — automate evidence collection for audits",
          "AWS Organizations — centrally manage multiple accounts with Service Control Policies (SCPs)",
          "SCPs — permission guardrails that override IAM policies across child accounts",
          "AWS Artifact — self-service portal for AWS compliance reports and agreements"
        ]
      },
      {
        heading: "Network Security",
        points: [
          "Security Groups — stateful instance-level firewall (allow rules only)",
          "Network ACLs — stateless subnet-level firewall (allow and deny rules)",
          "Encryption in transit — TLS/SSL for data moving between services",
          "Encryption at rest — KMS, S3 server-side encryption, EBS encryption",
          "AWS VPN — encrypted connection over the public internet to your VPC"
        ]
      },
      {
        heading: "Best Practices",
        points: [
          "Enable MFA on the root account and all IAM users",
          "Use IAM roles for EC2 instances instead of embedding access keys",
          "Rotate credentials regularly",
          "Use SCPs to enforce guardrails across accounts",
          "Encrypt data at rest (KMS, S3 encryption) and in transit (TLS/SSL)",
          "Enable CloudTrail in all Regions for complete audit logging",
          "Use AWS Trusted Advisor security checks for best practice recommendations"
        ]
      }
    ]
  },
  {
    domain: 3,
    title: "Technology & Services",
    weight: "34% of exam (~22 questions)",
    sections: [
      {
        heading: "Compute",
        points: [
          "Amazon EC2 — resizable virtual servers; choose instance type, OS, storage",
          "EC2 instance types — General Purpose, Compute Optimized, Memory Optimized, Storage Optimized, Accelerated Computing",
          "AWS Lambda — serverless functions; pay per invocation, no servers to manage",
          "AWS Elastic Beanstalk — deploy web apps automatically (handles provisioning, LB, scaling)",
          "Amazon Lightsail — simple VPS for small projects and quick launches",
          "EC2 Auto Scaling — automatically adjusts instance count based on demand",
          "Elastic Load Balancing (ELB) — distributes traffic across multiple targets (ALB, NLB, CLB)",
          "AWS Batch — run batch computing jobs on managed EC2 or Spot instances"
        ]
      },
      {
        heading: "Containers",
        points: [
          "Amazon ECS — managed container orchestration service",
          "Amazon EKS — managed Kubernetes service",
          "AWS Fargate — serverless compute for containers (no server management)",
          "Amazon ECR — managed Docker container registry"
        ]
      },
      {
        heading: "Storage",
        points: [
          "Amazon S3 — object storage; unlimited capacity, 11 nines durability",
          "S3 Storage Classes — Standard, Intelligent-Tiering, Standard-IA, One Zone-IA, Glacier Instant Retrieval, Glacier Flexible Retrieval, Glacier Deep Archive",
          "Amazon EBS — block storage volumes attached to EC2 instances",
          "EC2 Instance Store — temporary block storage physically attached to the host (ephemeral)",
          "Amazon EFS — managed file storage (NFS) shared across multiple EC2 instances",
          "Amazon FSx — managed file systems (Windows File Server, Lustre, NetApp ONTAP, OpenZFS)",
          "Amazon S3 Glacier — low-cost archival storage with retrieval options from minutes to hours",
          "AWS Storage Gateway — hybrid storage connecting on-premises to cloud storage",
          "AWS Backup — centralized backup service across AWS resources",
          "AWS Snowball / Snowball Edge — physical device for large-scale data transfer to AWS"
        ]
      },
      {
        heading: "Databases",
        points: [
          "Amazon RDS — managed relational DB (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server)",
          "Amazon Aurora — AWS-built relational DB, MySQL/PostgreSQL compatible, up to 5x faster",
          "Amazon DynamoDB — managed NoSQL (key-value), single-digit ms latency at any scale",
          "Amazon Redshift — data warehouse for analytics and BI queries",
          "Amazon ElastiCache — in-memory caching (Redis, Memcached)",
          "Amazon MemoryDB for Redis — durable in-memory database",
          "Amazon DocumentDB — managed document database (MongoDB compatible)",
          "Amazon Neptune — managed graph database",
          "Amazon Keyspaces — managed Apache Cassandra-compatible database",
          "Amazon QLDB — immutable, cryptographically verifiable ledger database",
          "AWS Database Migration Service (DMS) — migrate databases with minimal downtime",
          "AWS Schema Conversion Tool (SCT) — convert database schemas between engines"
        ]
      },
      {
        heading: "Networking & Content Delivery",
        points: [
          "Amazon VPC — isolated virtual network; subnets, route tables, gateways",
          "VPC components — public/private subnets, Internet Gateway, NAT Gateway, VPC Peering",
          "Amazon CloudFront — CDN; caches content at edge locations globally",
          "Amazon Route 53 — DNS service; domain registration, routing, health checks",
          "AWS Direct Connect — dedicated private network connection from on-premises to AWS",
          "AWS VPN — encrypted connection over the public internet to your VPC",
          "AWS Global Accelerator — routes traffic through AWS global network for better performance",
          "AWS Transit Gateway — connect multiple VPCs and on-premises networks through a central hub",
          "Security Groups — stateful instance-level firewall (allow rules only)",
          "Network ACLs — stateless subnet-level firewall (allow and deny rules)"
        ]
      },
      {
        heading: "Application Integration",
        points: [
          "Amazon SQS — message queue for decoupling microservices",
          "Amazon SNS — pub/sub notification service (email, SMS, Lambda triggers)",
          "Amazon EventBridge — serverless event bus for event-driven architectures",
          "AWS Step Functions — orchestrate workflows as state machines"
        ]
      },
      {
        heading: "AI/ML Services",
        points: [
          "Amazon SageMaker — fully managed platform for building, training, and deploying ML models",
          "Amazon Bedrock — build generative AI apps using foundation models (Claude, Llama, Titan)",
          "Amazon Q — AI assistant for business (Q Business) and development (Q Developer)",
          "Amazon Rekognition — image and video analysis (face detection, object recognition)",
          "Amazon Transcribe — speech to text (meeting transcription, subtitles)",
          "Amazon Polly — text to speech (accessibility, IVR systems)",
          "Amazon Translate — real-time language translation",
          "Amazon Comprehend — natural language processing (sentiment analysis, entity extraction)",
          "Amazon Lex — conversational interfaces / chatbots (powers Alexa)",
          "Amazon Textract — extract text and data from scanned documents",
          "Amazon Kendra — intelligent enterprise search across documents",
          "Amazon Personalize — real-time personalization and recommendations",
          "Amazon Forecast — time-series forecasting (demand planning, financial forecasting)"
        ]
      },
      {
        heading: "Analytics",
        points: [
          "Amazon Athena — serverless SQL queries directly on S3 data",
          "Amazon Kinesis — real-time data streaming (Data Streams, Firehose, Analytics, Video Streams)",
          "Amazon EMR — managed Hadoop/Spark clusters for big data processing",
          "Amazon QuickSight — serverless BI dashboards and visualizations",
          "AWS Glue — serverless ETL (Extract, Transform, Load) and data catalog",
          "AWS Lake Formation — create and manage data lakes on S3",
          "Amazon OpenSearch Service — search and log analytics (successor to Elasticsearch)"
        ]
      },
      {
        heading: "Management & Monitoring",
        points: [
          "Amazon CloudWatch — metrics, logs, alarms for AWS resources",
          "AWS CloudFormation — infrastructure as code (JSON/YAML templates)",
          "AWS CDK — define cloud infrastructure using programming languages",
          "AWS Systems Manager — operational management for EC2 fleets (patch, run commands)",
          "AWS Trusted Advisor — best practice recommendations (cost, security, performance, fault tolerance, service limits)",
          "AWS Health Dashboard — personalized view of AWS service health and events",
          "AWS Compute Optimizer — recommends optimal instance types based on usage",
          "AWS Config — track resource configurations and compliance",
          "AWS CloudTrail — API call logging and auditing",
          "AWS Service Catalog — create and manage approved IT service catalogs",
          "AWS Control Tower — set up and govern a multi-account AWS environment",
          "AWS License Manager — manage software licenses across AWS and on-premises"
        ]
      },
      {
        heading: "Developer Tools",
        points: [
          "AWS CodeCommit — managed Git repositories",
          "AWS CodeBuild — managed build service (compile, test, package)",
          "AWS CodeDeploy — automate code deployments to EC2, Lambda, ECS",
          "AWS CodePipeline — CI/CD pipeline orchestration",
          "AWS CodeStar — unified interface for software development projects",
          "AWS Cloud9 — cloud-based IDE",
          "AWS CloudShell — browser-based shell with AWS CLI pre-installed",
          "AWS X-Ray — distributed tracing for debugging microservices",
          "AWS CodeArtifact — managed artifact repository (npm, Maven, pip)",
          "AWS AppConfig — manage and deploy application configuration"
        ]
      },
      {
        heading: "Business & End-User Services",
        points: [
          "Amazon Connect — cloud-based contact center service",
          "Amazon SES — scalable email sending service",
          "Amazon WorkSpaces — managed virtual desktops (DaaS)",
          "Amazon AppStream 2.0 — stream desktop applications to any device",
          "AWS Amplify — build and deploy full-stack web and mobile apps",
          "AWS AppSync — managed GraphQL API service"
        ]
      },
      {
        heading: "IoT",
        points: [
          "AWS IoT Core — connect IoT devices to the cloud",
          "AWS IoT Greengrass — run local compute, messaging, and ML on edge devices"
        ]
      }
    ]
  },
  {
    domain: 4,
    title: "Billing, Pricing & Support",
    weight: "12% of exam (~8 questions)",
    sections: [
      {
        heading: "EC2 Pricing Models",
        points: [
          "On-Demand — pay per second (Linux) or per hour (Windows), no commitment",
          "Reserved Instances — 1 or 3 year commitment, up to 72% discount; best for steady workloads",
          "Savings Plans — flexible pricing; commit to $/hr of usage for 1 or 3 years",
          "Spot Instances — bid on unused capacity, up to 90% discount; can be interrupted",
          "Dedicated Hosts — physical server dedicated to you; for licensing or compliance requirements",
          "Dedicated Instances — run on hardware dedicated to you but AWS manages the host",
          "Capacity Reservations — reserve capacity in a specific AZ without a commitment discount"
        ]
      },
      {
        heading: "AWS Free Tier",
        points: [
          "Three types: Always Free, 12 Months Free, Trials",
          "Always Free examples: Lambda (1M requests/mo), DynamoDB (25 GB), SNS (1M publishes)",
          "12 Months Free examples: EC2 (750 hrs t2.micro/mo), S3 (5 GB), RDS (750 hrs t2.micro/mo)",
          "Monitor usage to avoid unexpected charges when free tier limits are exceeded"
        ]
      },
      {
        heading: "Cost Management Tools",
        points: [
          "AWS Cost Explorer — visualize and analyze spending over time with custom reports and forecasting",
          "AWS Budgets — set custom cost/usage thresholds and receive alerts (email, SNS)",
          "AWS Pricing Calculator — estimate costs for planned architectures before deploying",
          "AWS Cost Allocation Tags — tag resources to categorize costs by project, team, or environment",
          "AWS Cost and Usage Report — most detailed billing data, exportable to S3",
          "AWS Billing Conductor — customize billing and chargeback for different groups",
          "AWS Billing Dashboard — overview of current month charges and trends",
          "AWS Compute Optimizer — right-sizing recommendations to reduce costs"
        ]
      },
      {
        heading: "AWS Organizations & Consolidated Billing",
        points: [
          "Centrally manage multiple AWS accounts from a single management account",
          "Consolidated Billing — combines usage across accounts for volume pricing discounts",
          "Service Control Policies (SCPs) — set permission guardrails across all member accounts",
          "Organizational Units (OUs) — group accounts for applying policies",
          "Reserved Instance sharing — RIs can be shared across accounts in an Organization"
        ]
      },
      {
        heading: "Support Plans",
        points: [
          "Basic (free) — 24/7 customer service, documentation, forums, Trusted Advisor (core checks)",
          "Developer ($29/mo) — business hours email support, 1 primary contact",
          "Business ($100/mo+) — 24/7 phone/chat/email, full Trusted Advisor, unlimited contacts, AWS Health API",
          "Enterprise On-Ramp ($5,500/mo+) — TAM pool, concierge, 30-min critical response",
          "Enterprise ($15,000/mo+) — designated TAM, concierge support team, 15-min critical response, infrastructure event management"
        ]
      },
      {
        heading: "Key Pricing Principles",
        points: [
          "Pay as you go — no upfront costs, pay only for what you use",
          "Pay less when you reserve — commit for 1-3 years for significant discounts",
          "Pay less per unit by using more — volume discounts (e.g. S3 tiered pricing)",
          "No charge for inbound data transfer; outbound data transfer is charged",
          "Free services: IAM, VPC, Consolidated Billing, Elastic Beanstalk (pay for underlying resources)"
        ]
      },
      {
        heading: "Support Resources & Partner Network",
        points: [
          "AWS Trusted Advisor — automated best practice checks (cost, security, performance, fault tolerance, service limits)",
          "AWS Health Dashboard — personalized service health and scheduled maintenance alerts",
          "AWS Knowledge Center — FAQ-style answers to common questions",
          "AWS re:Post — community-driven Q&A (replaced AWS Forums)",
          "AWS Prescriptive Guidance — proven strategies and patterns for cloud adoption",
          "AWS Professional Services — consulting team for enterprise cloud projects",
          "AWS Solutions Architects — technical guidance for architecture design",
          "AWS Partner Network (APN) — ISVs and system integrators",
          "AWS Marketplace — buy and sell third-party software that runs on AWS",
          "AWS IQ — connect with AWS-certified freelance experts",
          "AWS Managed Services (AMS) — AWS operates your infrastructure on your behalf",
          "AWS Activate — resources and credits for startups",
          "AWS Trust and Safety — report abuse of AWS resources"
        ]
      }
    ]
  }
];
