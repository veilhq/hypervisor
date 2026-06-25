// ===================================================================
// CLF-C02 AWS Certified Cloud Practitioner — Question Bank
// ===================================================================
// Exam structure (per official AWS exam guide):
//   65 questions, 90 minutes, 700/1000 scaled score to pass (~72-75%)
//   50 scored + 15 unscored pretest questions
//   Two question types: multiple choice (1 correct of 4) and
//   multiple response (2-3 correct of 5-6, question states how many)
//
// Domain weights:
//   D1 Cloud Concepts .............. 24%  (~16 questions)
//   D2 Security and Compliance ..... 30%  (~20 questions)
//   D3 Cloud Technology and Services 34%  (~22 questions)
//   D4 Billing, Pricing, and Support 12%  (~8 questions)
//
// Question format:
//   d    = domain (1-4)
//   t    = type: "recall" or "scenario"
//   q    = question text
//   o    = options array
//   a    = correct answer index (single) OR array of indices (multi)
//   e    = explanation
//   pick = number of answers to select for multi-response (absent = single)
//
// To add questions: append to the appropriate domain section below.
// Answer index (a) should be distributed across 0-3 for single-select.
// ===================================================================

// Generic name for the assessment engine (aliased from CCP_QUESTIONS for backward compat)
window.QUIZ_QUESTIONS = [

  // ================================================================
  // DOMAIN 1 — Cloud Concepts (24%)
  // ================================================================

  // -- Recall --
  {d:1, t:"recall", q:"Which cloud computing model provides the MOST control over the underlying IT resources?",
   o:["Software as a Service (SaaS)","Platform as a Service (PaaS)","Infrastructure as a Service (IaaS)","Function as a Service (FaaS)"],
   a:2, e:"IaaS gives customers the highest level of control over networking, storage, and compute, similar to traditional on-premises infrastructure."},

  {d:1, t:"recall", q:"What does the 'elasticity' of the AWS Cloud refer to?",
   o:["The ability to create IAM users on demand","The ability to acquire resources as needed and release them when no longer required","The ability to use reserved instances for cost savings","The ability to run applications in multiple AWS Regions"],
   a:1, e:"Elasticity is the ability to automatically scale resources up or down to match demand, so you only use what you need."},

  {d:1, t:"recall", q:"Which pillar of the AWS Well-Architected Framework focuses on running and monitoring systems to deliver business value?",
   o:["Security","Reliability","Operational Excellence","Performance Efficiency"],
   a:2, e:"Operational Excellence focuses on running and monitoring systems to deliver business value and continually improve supporting processes and procedures."},

  {d:1, t:"recall", q:"What is the primary purpose of AWS Regions?",
   o:["To separate development and production environments","To provide different pricing tiers for services","To provide geographically isolated locations for deploying resources","To manage IAM users and groups"],
   a:2, e:"AWS Regions are separate geographic areas that let you place resources closer to users and meet data residency requirements."},

  {d:1, t:"recall", q:"Which deployment model connects on-premises infrastructure to cloud resources?",
   o:["Public cloud","Private cloud","Hybrid cloud","Multi-cloud"],
   a:2, e:"Hybrid cloud connects on-premises infrastructure to cloud resources, allowing workloads to span both environments."},

  {d:1, t:"recall", q:"What does 'high availability' mean in cloud computing?",
   o:["A system uses the cheapest resources available","A system is designed to operate continuously with minimal downtime","A system runs in a single data center for simplicity","A system requires manual intervention to recover from failures"],
   a:1, e:"High availability means a system is designed to be operational and accessible with minimal downtime, typically through redundancy across multiple locations."},

  {d:1, t:"recall", q:"Which of the following BEST describes the concept of 'pay-as-you-go' pricing?",
   o:["You pay a fixed monthly fee regardless of usage","You pay upfront for a year of service","You pay based on the number of employees in your organization","You pay only for the resources you actually consume"],
   a:3, e:"Pay-as-you-go means you are charged based on actual consumption with no long-term contracts or upfront commitments required."},

  // -- Scenario --
  {d:1, t:"scenario", q:"A startup wants to launch a new web application but is unsure how much traffic it will receive. They want to avoid purchasing expensive hardware that may go unused. Which advantage of cloud computing BEST addresses this concern?",
   o:["Go global in minutes","Trade fixed expense for variable expense","Benefit from massive economies of scale","Increase speed and agility"],
   a:1, e:"Trading fixed expense (buying servers) for variable expense (paying for what you use) means the startup avoids large upfront hardware investments and pays only for actual consumption."},

  {d:1, t:"scenario", q:"A company needs to deploy an application that must remain available even if an entire data center experiences an outage. What should the company do?",
   o:["Deploy the application in a single Availability Zone with larger instances","Deploy the application across multiple Availability Zones","Deploy the application on a single dedicated host","Store the application code in Amazon S3"],
   a:1, e:"Deploying across multiple Availability Zones provides fault tolerance. If one AZ fails, the application continues running in another AZ within the same Region."},

  {d:1, t:"scenario", q:"A company is evaluating whether to migrate to the cloud. The CTO wants to understand the AWS shared responsibility model. Which statement accurately describes it?",
   o:["AWS manages all security, and the customer manages billing","The customer manages all security, and AWS manages billing","AWS manages security OF the cloud infrastructure; the customer manages security IN the cloud","Security responsibilities are shared equally with no clear division"],
   a:2, e:"Under the shared responsibility model, AWS is responsible for the infrastructure (hardware, software, networking, facilities), while customers are responsible for their data, configurations, encryption, and access management."},

  {d:1, t:"scenario", q:"A retail company experiences a large spike in web traffic every November during holiday sales, then traffic drops significantly in January. Which cloud computing benefit is MOST relevant?",
   o:["Stop spending money running and maintaining data centers","Benefit from massive economies of scale","Stop guessing capacity","Go global in minutes"],
   a:2, e:"Stop guessing capacity means you can scale resources to match actual demand. The company can scale up for November traffic and scale down in January, avoiding over-provisioning."},

  {d:1, t:"scenario", q:"A company wants to experiment with new features quickly without large upfront investments. Which advantage of cloud computing supports this?",
   o:["Benefit from massive economies of scale","Trade fixed expense for variable expense","Increase speed and agility","Deploy globally in minutes"],
   a:2, e:"Cloud agility means you can quickly provision resources, experiment, and iterate without large upfront investments or long procurement cycles."},

  // -- Multi-select --
  {d:1, t:"recall", q:"Which TWO are benefits of cloud computing? (Select TWO)",
   o:["Trade fixed expense for variable expense","Maintain physical data centers on-premises","Benefit from massive economies of scale","Increase time required to deploy new resources","Require long-term contracts for all services"],
   a:[0,2], pick:2, e:"Cloud computing lets you pay only for what you use (variable expense) and benefit from AWS aggregating usage across customers for lower prices (economies of scale)."},

  {d:1, t:"recall", q:"Which TWO are pillars of the AWS Well-Architected Framework? (Select TWO)",
   o:["Cost Optimization","Elasticity","Sustainability","Agility","Economies of Scale"],
   a:[0,2], pick:2, e:"The six pillars are: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, and Sustainability. Elasticity, Agility, and Economies of Scale are cloud benefits, not framework pillars."},

  // ================================================================
  // DOMAIN 2 — Security and Compliance (30%)
  // ================================================================

  // -- Recall --
  {d:2, t:"recall", q:"What is the purpose of AWS Identity and Access Management (IAM)?",
   o:["To monitor application performance metrics","To manage access to AWS services and resources securely","To deploy applications to EC2 instances","To manage billing and cost allocation"],
   a:1, e:"IAM enables you to manage access to AWS services and resources securely using users, groups, roles, and policies."},

  {d:2, t:"recall", q:"Which AWS service provides managed DDoS protection?",
   o:["AWS WAF","Amazon Inspector","AWS Shield","AWS Config"],
   a:2, e:"AWS Shield provides managed DDoS protection. Shield Standard is automatic and free for all AWS customers; Shield Advanced provides enhanced protections for an additional fee."},

  {d:2, t:"recall", q:"What does AWS CloudTrail do?",
   o:["Monitors application performance in real time","Provides DDoS protection for web applications","Manages encryption keys across AWS services","Records API calls made on your AWS account for auditing"],
   a:3, e:"CloudTrail records AWS API calls for your account, providing a history of API activity for security analysis, resource change tracking, and compliance auditing."},

  {d:2, t:"recall", q:"Which AWS service continuously monitors for malicious activity and unauthorized behavior?",
   o:["AWS Trusted Advisor","Amazon CloudWatch","Amazon GuardDuty","AWS Config"],
   a:2, e:"Amazon GuardDuty is a threat detection service that continuously monitors for malicious activity and unauthorized behavior using machine learning and threat intelligence."},

  {d:2, t:"recall", q:"What is the principle of least privilege?",
   o:["Granting full access to all users for convenience","Granting access based on job seniority","Granting only the minimum permissions required to perform a task","Granting temporary access to all resources during onboarding"],
   a:2, e:"Least privilege means giving users only the minimum permissions they need to do their job, reducing the potential attack surface."},

  {d:2, t:"recall", q:"Which AWS service enables you to create and manage cryptographic keys?",
   o:["Amazon Macie","AWS Key Management Service (KMS)","Amazon Inspector","AWS Certificate Manager"],
   a:1, e:"AWS KMS lets you create and manage cryptographic keys and control their use across AWS services and in your applications."},

  {d:2, t:"recall", q:"What is multi-factor authentication (MFA)?",
   o:["A method of encrypting data at rest in S3","A backup strategy for disaster recovery","An authentication method requiring two or more verification factors","A way to create multiple IAM users simultaneously"],
   a:2, e:"MFA adds an extra layer of security by requiring something you know (password) plus something you have (MFA device) to authenticate."},

  {d:2, t:"recall", q:"Which service discovers and protects sensitive data stored in Amazon S3?",
   o:["Amazon Inspector","AWS CloudTrail","Amazon Macie","AWS Config"],
   a:2, e:"Amazon Macie uses machine learning to automatically discover, classify, and protect sensitive data such as PII stored in S3 buckets."},

  {d:2, t:"recall", q:"What does AWS WAF protect against?",
   o:["DDoS attacks at the network layer","Unauthorized API calls to your account","Data loss from S3 buckets","Common web exploits like SQL injection and cross-site scripting"],
   a:3, e:"AWS WAF is a web application firewall that helps protect web applications from common web exploits that could affect availability or consume excessive resources."},

  {d:2, t:"recall", q:"What is AWS Organizations used for?",
   o:["Managing EC2 instance fleets","Centrally managing and governing multiple AWS accounts","Monitoring application logs across services","Creating and managing VPCs"],
   a:1, e:"AWS Organizations lets you centrally manage billing, control access, compliance, and security across multiple AWS accounts using service control policies (SCPs)."},

  // -- Scenario --
  {d:2, t:"scenario", q:"A company's security team needs to investigate which IAM user deleted an S3 bucket last Tuesday. Which AWS service should they use?",
   o:["Amazon CloudWatch","AWS CloudTrail","Amazon GuardDuty","AWS Config"],
   a:1, e:"CloudTrail records API calls made on your account, including who made the call, when, and from where. It is the primary tool for investigating specific API actions."},

  {d:2, t:"scenario", q:"A company wants to ensure that no IAM user in a child account can launch EC2 instances in any Region other than us-east-1. Which AWS feature should they use?",
   o:["IAM user policies","Security groups","Service control policies (SCPs) in AWS Organizations","Network ACLs"],
   a:2, e:"SCPs in AWS Organizations set permission guardrails across accounts. They can restrict which Regions and services are available, regardless of individual IAM policies."},

  {d:2, t:"scenario", q:"An application running on EC2 needs to read objects from an S3 bucket. What is the MOST secure way to grant this access?",
   o:["Store AWS access keys in the application's environment variables","Attach an IAM role with an S3 read policy to the EC2 instance","Create an IAM user and embed the credentials in the application code","Make the S3 bucket public so the application can access it"],
   a:1, e:"IAM roles provide temporary credentials that are automatically rotated. Attaching a role to an EC2 instance is more secure than embedding long-term access keys."},

  {d:2, t:"scenario", q:"A company needs to verify that their AWS environment meets PCI DSS compliance requirements. Which AWS service provides automated security assessments?",
   o:["AWS Trusted Advisor","Amazon Inspector","AWS Shield","Amazon GuardDuty"],
   a:1, e:"Amazon Inspector automatically assesses applications for vulnerabilities and deviations from best practices, including checks against common compliance frameworks."},

  {d:2, t:"scenario", q:"A developer accidentally committed AWS access keys to a public GitHub repository. What should the security team do FIRST?",
   o:["Delete the GitHub repository","Rotate the exposed access keys immediately in IAM","Create a new AWS account","Enable AWS Shield Advanced"],
   a:1, e:"The immediate priority is to rotate (deactivate and replace) the compromised credentials to prevent unauthorized access. Then investigate any unauthorized usage via CloudTrail."},

  {d:2, t:"scenario", q:"A company wants to enforce that all S3 buckets across all accounts have encryption enabled. Which AWS service can continuously evaluate this?",
   o:["Amazon GuardDuty","AWS CloudTrail","AWS Config","Amazon Macie"],
   a:2, e:"AWS Config continuously evaluates resource configurations against rules you define. You can create a rule requiring S3 bucket encryption and Config will flag non-compliant buckets."},

  // -- Multi-select --
  {d:2, t:"scenario", q:"Under the AWS shared responsibility model, which TWO are the customer's responsibility? (Select TWO)",
   o:["Patching the hypervisor on EC2 host machines","Configuring security group rules","Managing the global network infrastructure","Encrypting data at rest in S3","Physical security of data centers"],
   a:[1,3], pick:2, e:"Customers are responsible for configuring their own security groups and encrypting their data. AWS handles the hypervisor, physical security, and global network infrastructure."},

  {d:2, t:"recall", q:"Which TWO AWS services are used for threat detection and monitoring? (Select TWO)",
   o:["Amazon GuardDuty","AWS Pricing Calculator","Amazon Macie","AWS Elastic Beanstalk","Amazon CloudFront"],
   a:[0,2], pick:2, e:"GuardDuty monitors for malicious activity and unauthorized behavior. Macie monitors S3 for sensitive data exposure. The others are unrelated to threat detection."},

  // ================================================================
  // DOMAIN 3 — Cloud Technology and Services (34%)
  // ================================================================

  // -- Recall --
  {d:3, t:"recall", q:"Which AWS service provides resizable virtual servers in the cloud?",
   o:["Amazon S3","AWS Lambda","Amazon EC2","Amazon RDS"],
   a:2, e:"Amazon EC2 (Elastic Compute Cloud) provides scalable virtual servers (instances) that you can configure with your choice of OS, CPU, memory, and storage."},

  {d:3, t:"recall", q:"Which AWS service is a fully managed relational database?",
   o:["Amazon DynamoDB","Amazon Redshift","Amazon S3","Amazon RDS"],
   a:3, e:"Amazon RDS makes it easy to set up, operate, and scale relational databases (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server) in the cloud."},

  {d:3, t:"recall", q:"What is Amazon S3 used for?",
   o:["Running serverless functions","Block-level storage for EC2","Object storage for any amount of data","Managed relational databases"],
   a:2, e:"Amazon S3 (Simple Storage Service) is object storage built to store and retrieve any amount of data from anywhere on the web."},

  {d:3, t:"recall", q:"Which AWS service runs code without provisioning or managing servers?",
   o:["Amazon EC2","Amazon ECS","AWS Elastic Beanstalk","AWS Lambda"],
   a:3, e:"AWS Lambda lets you run code without provisioning servers. You pay only for the compute time consumed, billed per millisecond."},

  {d:3, t:"recall", q:"What is Amazon VPC?",
   o:["A content delivery network for global distribution","A managed database service for MySQL","A logically isolated section of the AWS Cloud for launching resources","A monitoring service for application metrics"],
   a:2, e:"Amazon VPC lets you provision a logically isolated virtual network where you define IP ranges, subnets, route tables, and gateways."},

  {d:3, t:"recall", q:"Which AWS service provides a content delivery network (CDN)?",
   o:["Amazon Route 53","Amazon CloudFront","AWS Direct Connect","Amazon VPC"],
   a:1, e:"CloudFront is a CDN that caches content at edge locations worldwide, delivering data, videos, applications, and APIs with low latency."},

  {d:3, t:"recall", q:"Which AWS service provides a fully managed NoSQL database?",
   o:["Amazon RDS","Amazon Aurora","Amazon Redshift","Amazon DynamoDB"],
   a:3, e:"DynamoDB is a fully managed NoSQL database service that provides single-digit millisecond performance at any scale."},

  {d:3, t:"recall", q:"What is Amazon Route 53?",
   o:["A compute service for containers","A scalable DNS web service","A block storage service","A data warehouse solution"],
   a:1, e:"Route 53 is a highly available and scalable DNS web service for domain registration, DNS routing, and health checking."},

  {d:3, t:"recall", q:"Which AWS service provides block-level storage volumes for EC2 instances?",
   o:["Amazon S3","Amazon EFS","Amazon EBS","Amazon S3 Glacier"],
   a:2, e:"Amazon EBS (Elastic Block Store) provides persistent block-level storage volumes designed for use with EC2 instances."},

  {d:3, t:"recall", q:"What does Amazon CloudWatch do?",
   o:["Manages user access and permissions","Provides object storage","Monitors AWS resources and applications in real time","Runs serverless functions"],
   a:2, e:"CloudWatch collects monitoring and operational data as logs, metrics, and events, giving you a unified view of AWS resources and applications."},

  {d:3, t:"recall", q:"Which AWS service is a fully managed message queuing service?",
   o:["Amazon SNS","Amazon Kinesis","Amazon SQS","AWS Step Functions"],
   a:2, e:"Amazon SQS (Simple Queue Service) is a fully managed message queuing service for decoupling and scaling microservices and distributed systems."},

  {d:3, t:"recall", q:"What is AWS Elastic Beanstalk?",
   o:["A serverless compute service","A container orchestration service","A database migration service","A service for deploying and scaling web applications automatically"],
   a:3, e:"Elastic Beanstalk handles deployment, capacity provisioning, load balancing, and auto-scaling for web applications. You upload your code and it handles the rest."},

  {d:3, t:"recall", q:"Which AWS service provides a managed Kubernetes service?",
   o:["Amazon ECS","AWS Fargate","Amazon EKS","AWS Lambda"],
   a:2, e:"Amazon EKS (Elastic Kubernetes Service) is a managed service for running Kubernetes on AWS without needing to install and operate your own control plane."},

  {d:3, t:"recall", q:"What is AWS Direct Connect?",
   o:["A VPN service for encrypted internet connections","A CDN service for content distribution","A DNS service for domain management","A dedicated private network connection from your premises to AWS"],
   a:3, e:"Direct Connect establishes a dedicated private network connection from your data center to AWS, bypassing the public internet for more consistent performance."},

  {d:3, t:"recall", q:"Which AWS service is a data warehouse solution?",
   o:["Amazon RDS","Amazon DynamoDB","Amazon ElastiCache","Amazon Redshift"],
   a:3, e:"Amazon Redshift is a fast, scalable data warehouse that makes it simple to analyze data using standard SQL and existing BI tools."},

  {d:3, t:"recall", q:"What is Amazon Aurora?",
   o:["A NoSQL database for key-value workloads","An in-memory caching service","A MySQL and PostgreSQL-compatible relational database built for the cloud","A data streaming service"],
   a:2, e:"Aurora is a MySQL/PostgreSQL-compatible relational database with up to 5x the throughput of standard MySQL and 3x the throughput of standard PostgreSQL."},

  // -- Scenario --
  {d:3, t:"scenario", q:"A company needs to run a batch processing job that can be interrupted and restarted without data loss. The job processes large datasets overnight. Which compute service is MOST cost-effective?",
   o:["Amazon EC2 On-Demand Instances","AWS Lambda","Amazon EC2 Spot Instances","Amazon Lightsail"],
   a:2, e:"Spot Instances offer up to 90% discount compared to On-Demand pricing and are ideal for fault-tolerant, interruptible workloads like batch processing."},

  {d:3, t:"scenario", q:"A company wants to host a static website with global low-latency access. Which combination of services should they use?",
   o:["Amazon EC2 and Elastic Load Balancing","Amazon S3 and Amazon CloudFront","Amazon RDS and Amazon Route 53","AWS Lambda and Amazon API Gateway"],
   a:1, e:"S3 can host static websites, and CloudFront distributes the content globally via edge locations for low-latency access worldwide."},

  {d:3, t:"scenario", q:"A mobile application needs to store user profile data with single-digit millisecond read latency. The data model uses simple key-value lookups. Which database service is MOST appropriate?",
   o:["Amazon RDS for MySQL","Amazon Redshift","Amazon DynamoDB","Amazon Aurora"],
   a:2, e:"DynamoDB is a NoSQL database optimized for key-value and document workloads with single-digit millisecond performance at any scale."},

  {d:3, t:"scenario", q:"A company runs a web application on EC2 instances behind an Application Load Balancer. Traffic varies significantly throughout the day. Which AWS feature should they use to automatically adjust the number of instances?",
   o:["AWS CloudFormation","Amazon CloudFront","Amazon EC2 Auto Scaling","AWS Elastic Beanstalk"],
   a:2, e:"EC2 Auto Scaling automatically adjusts the number of EC2 instances based on demand, scaling out during traffic spikes and scaling in during quiet periods."},

  {d:3, t:"scenario", q:"A company needs to migrate 50 TB of data from an on-premises data center to Amazon S3. Their internet connection is too slow for a timely transfer. Which AWS service should they use?",
   o:["AWS Direct Connect","AWS DataSync","AWS Snowball Edge","Amazon Kinesis"],
   a:2, e:"AWS Snowball Edge is a physical device shipped to your location for transferring large amounts of data to AWS when network transfer is impractical."},

  {d:3, t:"scenario", q:"A development team needs to deploy a containerized microservices application but does not want to manage the underlying server infrastructure. Which AWS service should they use?",
   o:["Amazon EC2","Amazon ECS with AWS Fargate","AWS Elastic Beanstalk","Amazon Lightsail"],
   a:1, e:"ECS with Fargate runs containers without requiring you to manage servers or clusters. Fargate handles the infrastructure so you focus on your application."},

  {d:3, t:"scenario", q:"A company wants to run short-lived functions triggered by API requests, processing each request in under 3 seconds. They want to pay only when code is executing. Which service fits BEST?",
   o:["Amazon EC2 On-Demand","Amazon ECS","AWS Lambda","Amazon Lightsail"],
   a:2, e:"Lambda is ideal for short-lived, event-driven functions. You pay only for the compute time consumed, with no charge when code is not running."},

  // -- Multi-select --
  {d:3, t:"scenario", q:"A company needs to choose a database service for their application. Which TWO are managed relational database services on AWS? (Select TWO)",
   o:["Amazon DynamoDB","Amazon RDS","Amazon ElastiCache","Amazon Aurora","Amazon Redshift"],
   a:[1,3], pick:2, e:"RDS and Aurora are both managed relational database services. DynamoDB is NoSQL, ElastiCache is in-memory caching, and Redshift is a data warehouse."},

  {d:3, t:"recall", q:"Which TWO are serverless AWS services? (Select TWO)",
   o:["Amazon EC2","AWS Lambda","Amazon RDS","AWS Fargate","Amazon Redshift"],
   a:[1,3], pick:2, e:"Lambda runs code without servers, and Fargate runs containers without managing server infrastructure. EC2, RDS, and Redshift all involve provisioned infrastructure."},

  {d:3, t:"recall", q:"Which TWO AWS services can be used for application integration and decoupling? (Select TWO)",
   o:["Amazon SQS","Amazon EC2","Amazon SNS","Amazon EBS","Amazon VPC"],
   a:[0,2], pick:2, e:"SQS (message queuing) and SNS (pub/sub notifications) are both used to decouple application components. The others are compute, storage, and networking services."},

  // ================================================================
  // DOMAIN 4 — Billing, Pricing, and Support (12%)
  // ================================================================

  // -- Recall --
  {d:4, t:"recall", q:"Which AWS support plan provides access to a designated Technical Account Manager (TAM)?",
   o:["Basic","Developer","Business","Enterprise"],
   a:3, e:"Only the Enterprise support plan includes a designated Technical Account Manager who provides proactive guidance."},

  {d:4, t:"recall", q:"What is the AWS Free Tier?",
   o:["A support plan for new customers","A set of free offers for new and existing customers to try AWS services within certain usage limits","A pricing model exclusively for reserved instances","A billing alert system for cost management"],
   a:1, e:"The AWS Free Tier includes three types of offers: always free, 12 months free, and trials, allowing customers to explore services within defined usage limits."},

  {d:4, t:"recall", q:"Which tool provides a visual interface to understand and manage AWS costs and usage over time?",
   o:["AWS Budgets","AWS Pricing Calculator","AWS Billing Dashboard","AWS Cost Explorer"],
   a:3, e:"Cost Explorer lets you visualize, understand, and manage your AWS costs and usage over time with custom reports and forecasting."},

  {d:4, t:"recall", q:"What is the benefit of Reserved Instances compared to On-Demand?",
   o:["They are always free of charge","They provide the highest possible performance","They offer significant discounts in exchange for a 1 or 3 year commitment","They are only available in a single AWS Region"],
   a:2, e:"Reserved Instances provide up to 72% discount compared to On-Demand pricing when you commit to a 1 or 3 year term."},

  {d:4, t:"recall", q:"What is AWS Consolidated Billing?",
   o:["A way to pay for a single EC2 instance over time","A pricing model for S3 storage classes","A feature of AWS Organizations that combines billing across multiple accounts","A support plan feature for cost optimization"],
   a:2, e:"Consolidated Billing combines usage across all accounts in an organization, potentially qualifying for volume pricing discounts."},

  {d:4, t:"recall", q:"What does the AWS Basic support plan include?",
   o:["Access to a Technical Account Manager","Infrastructure event management","24/7 access to customer service, documentation, whitepapers, and support forums","Concierge support team"],
   a:2, e:"The Basic plan is free for all AWS customers and includes 24/7 customer service, documentation, whitepapers, and support forums."},

  {d:4, t:"recall", q:"What is the purpose of AWS Cost Allocation Tags?",
   o:["To tag EC2 instances for security group assignment","To manage IAM permissions by resource","To categorize and track AWS costs by project, team, or environment","To configure VPC routing tables"],
   a:2, e:"Cost allocation tags let you organize your resource costs on your cost allocation report, making it easier to categorize and track spending."},

  // -- Scenario --
  {d:4, t:"scenario", q:"A company runs a web server that must be available 24/7 for the next 3 years. The workload is steady and predictable. Which EC2 pricing model is MOST cost-effective?",
   o:["On-Demand Instances","Spot Instances","Reserved Instances","Dedicated Hosts"],
   a:2, e:"Reserved Instances are ideal for steady, predictable workloads with a known duration. A 3-year commitment provides the deepest discount."},

  {d:4, t:"scenario", q:"A data science team needs to run large compute jobs that can tolerate interruptions. They want the lowest possible cost. Which EC2 pricing model should they use?",
   o:["On-Demand Instances","Reserved Instances","Spot Instances","Savings Plans"],
   a:2, e:"Spot Instances offer up to 90% discount for workloads that can tolerate interruptions, making them the cheapest option for fault-tolerant batch processing."},

  {d:4, t:"scenario", q:"A company wants to receive an alert when their monthly AWS spending exceeds $5,000. Which AWS service should they use?",
   o:["AWS Cost Explorer","AWS Trusted Advisor","AWS Budgets","AWS Pricing Calculator"],
   a:2, e:"AWS Budgets lets you set custom cost thresholds and receive alerts via email or SNS when actual or forecasted spending exceeds your defined budget."},

  {d:4, t:"scenario", q:"A company with 10 AWS accounts wants to take advantage of volume pricing discounts. What should they do?",
   o:["Contact AWS support to request a discount","Use AWS Organizations with consolidated billing","Purchase Reserved Instances in each account separately","Enable AWS Cost Explorer in each account"],
   a:1, e:"AWS Organizations with consolidated billing aggregates usage across all member accounts, which can qualify the organization for volume pricing tiers."},

  {d:4, t:"scenario", q:"A company is planning a new architecture and wants to estimate the monthly cost before deploying anything. Which AWS tool should they use?",
   o:["AWS Cost Explorer","AWS Budgets","AWS Pricing Calculator","AWS Trusted Advisor"],
   a:2, e:"The AWS Pricing Calculator lets you explore AWS services and create an estimate for the cost of your planned architecture before you deploy."},

  // -- Multi-select --
  {d:4, t:"recall", q:"Which TWO are valid EC2 pricing models? (Select TWO)",
   o:["Pay-per-query","On-Demand Instances","Spot Instances","Free Tier Instances","Subscription Instances"],
   a:[1,2], pick:2, e:"On-Demand (pay by the second with no commitment) and Spot (bid on unused capacity at steep discounts) are both valid EC2 pricing models."},

  {d:4, t:"recall", q:"Which TWO AWS tools help with cost management and optimization? (Select TWO)",
   o:["Amazon GuardDuty","AWS Budgets","Amazon Inspector","AWS Cost Explorer","AWS Shield"],
   a:[1,3], pick:2, e:"AWS Budgets sets spending alerts and AWS Cost Explorer visualizes and analyzes spending. The others are security services."},

  // ================================================================
  // ADDITIONAL QUESTIONS — CLF-C02 coverage gaps
  // ================================================================

  // -- D1: Migration & Cloud Adoption --
  {d:1, t:"recall", q:"What is the AWS Cloud Adoption Framework (AWS CAF)?",
   o:["A pricing model for enterprise customers","Guidance to help organizations plan their cloud migration across six perspectives","A tool for deploying EC2 instances","An AWS support plan for startups"],
   a:1, e:"AWS CAF provides guidance across six perspectives (Business, People, Governance, Platform, Security, Operations) to help organizations plan and execute cloud adoption."},

  {d:1, t:"scenario", q:"A company wants to migrate its on-premises applications to AWS with minimal changes. Which migration strategy should they use?",
   o:["Refactor (re-architect)","Rehost (lift and shift)","Retire","Repurchase (drop and shop)"],
   a:1, e:"Rehost (lift and shift) moves applications to the cloud with minimal or no changes, making it the fastest migration path."},

  {d:1, t:"recall", q:"Which AWS service provides a central location to track the progress of application migrations?",
   o:["AWS CloudFormation","AWS Migration Hub","AWS Config","Amazon CloudWatch"],
   a:1, e:"AWS Migration Hub provides a single place to track the progress of application migrations across multiple AWS and partner tools."},

  {d:1, t:"scenario", q:"A company wants to migrate an on-premises Oracle database to Amazon Aurora PostgreSQL. Which AWS tools should they use?",
   o:["AWS Snowball and Amazon S3","AWS DMS and AWS Schema Conversion Tool","Amazon Redshift and AWS Glue","AWS Lambda and Amazon RDS"],
   a:1, e:"AWS DMS handles the data migration with minimal downtime, and AWS SCT converts the database schema from Oracle to PostgreSQL format."},

  {d:1, t:"recall", q:"Which concept describes converting capital expenditure (CapEx) to operational expenditure (OpEx) by moving to the cloud?",
   o:["Rightsizing","Trade fixed expense for variable expense","Economies of scale","Elasticity"],
   a:1, e:"Cloud computing converts upfront capital expenses (buying servers) into variable operational expenses (paying for what you use), reducing financial risk."},

  // -- D2: Additional Security Services --
  {d:2, t:"recall", q:"Which AWS service aggregates security findings from GuardDuty, Inspector, Macie, and other services into a single dashboard?",
   o:["AWS CloudTrail","Amazon Detective","AWS Security Hub","AWS Config"],
   a:2, e:"AWS Security Hub provides a comprehensive view of security alerts and compliance status by aggregating findings from multiple AWS security services."},

  {d:2, t:"recall", q:"Which AWS service helps you securely store, rotate, and manage database credentials and API keys?",
   o:["AWS KMS","AWS Secrets Manager","AWS Certificate Manager","Amazon Macie"],
   a:1, e:"AWS Secrets Manager helps you protect access to applications and services by securely storing and automatically rotating secrets like database credentials and API keys."},

  {d:2, t:"recall", q:"Which AWS service provides centralized single sign-on access to multiple AWS accounts and business applications?",
   o:["AWS Organizations","IAM Identity Center (AWS SSO)","Amazon Cognito","AWS Directory Service"],
   a:1, e:"IAM Identity Center (formerly AWS SSO) provides centralized single sign-on access to multiple AWS accounts and business applications from one place."},

  {d:2, t:"scenario", q:"A security analyst needs to investigate a potential security incident by analyzing VPC flow logs, CloudTrail events, and GuardDuty findings together. Which service helps with this?",
   o:["AWS Security Hub","Amazon Detective","AWS Config","Amazon Inspector"],
   a:1, e:"Amazon Detective automatically collects and analyzes data from VPC flow logs, CloudTrail, and GuardDuty to help investigate and identify the root cause of security issues."},

  {d:2, t:"recall", q:"Where can a customer download AWS compliance reports such as SOC and PCI DSS?",
   o:["AWS Trusted Advisor","AWS Artifact","AWS Config","AWS Security Hub"],
   a:1, e:"AWS Artifact is a self-service portal for on-demand access to AWS compliance reports and select online agreements."},

  // -- D3: AI/ML Services --
  {d:3, t:"recall", q:"Which AWS service is a fully managed platform for building, training, and deploying machine learning models?",
   o:["Amazon Bedrock","Amazon Rekognition","Amazon SageMaker","Amazon Comprehend"],
   a:2, e:"Amazon SageMaker provides a fully managed environment for the entire ML workflow: data preparation, model training, tuning, and deployment."},

  {d:3, t:"recall", q:"Which AWS service provides access to foundation models for building generative AI applications?",
   o:["Amazon SageMaker","Amazon Bedrock","Amazon Lex","Amazon Personalize"],
   a:1, e:"Amazon Bedrock provides access to foundation models from leading AI providers (Claude, Llama, Titan) for building generative AI applications without managing infrastructure."},

  {d:3, t:"scenario", q:"A company wants to add automatic subtitle generation to their video content. Which AWS service should they use?",
   o:["Amazon Polly","Amazon Translate","Amazon Transcribe","Amazon Comprehend"],
   a:2, e:"Amazon Transcribe converts speech to text, making it ideal for generating subtitles, meeting transcriptions, and call center analytics."},

  {d:3, t:"scenario", q:"A company wants to build a chatbot for customer service on their website. Which AWS service should they use?",
   o:["Amazon Polly","Amazon Lex","Amazon Comprehend","Amazon Kendra"],
   a:1, e:"Amazon Lex provides the technology to build conversational interfaces (chatbots) using voice and text. It powers Amazon Alexa."},

  {d:3, t:"scenario", q:"A retail company wants to add personalized product recommendations to their website. Which AWS service should they use?",
   o:["Amazon Forecast","Amazon Personalize","Amazon Comprehend","Amazon Kendra"],
   a:1, e:"Amazon Personalize uses ML to deliver real-time personalized recommendations for products, content, and search results."},

  {d:3, t:"scenario", q:"A company needs to analyze customer reviews to determine whether sentiment is positive, negative, or neutral. Which AWS service should they use?",
   o:["Amazon Lex","Amazon Textract","Amazon Comprehend","Amazon Rekognition"],
   a:2, e:"Amazon Comprehend is a natural language processing (NLP) service that can identify sentiment, entities, key phrases, and language in text."},

  // -- D3: Analytics --
  {d:3, t:"recall", q:"Which AWS service lets you run SQL queries directly against data stored in Amazon S3 without loading it into a database?",
   o:["Amazon Redshift","Amazon RDS","Amazon Athena","Amazon DynamoDB"],
   a:2, e:"Amazon Athena is a serverless interactive query service that uses standard SQL to analyze data directly in S3. You pay per query based on data scanned."},

  {d:3, t:"recall", q:"Which AWS service provides real-time data streaming capabilities?",
   o:["Amazon SQS","Amazon Kinesis","Amazon Athena","AWS Glue"],
   a:1, e:"Amazon Kinesis is a platform for real-time streaming data. It can collect, process, and analyze data streams in real time."},

  {d:3, t:"recall", q:"Which AWS service is a serverless ETL service that discovers, prepares, and combines data for analytics?",
   o:["Amazon Athena","Amazon EMR","AWS Glue","Amazon Redshift"],
   a:2, e:"AWS Glue is a serverless data integration service for ETL. It includes a Data Catalog for metadata management and crawlers for automatic schema discovery."},

  {d:3, t:"recall", q:"Which AWS service provides serverless business intelligence dashboards and visualizations?",
   o:["Amazon Athena","Amazon QuickSight","Amazon CloudWatch","AWS Glue"],
   a:1, e:"Amazon QuickSight is a serverless BI service that creates interactive dashboards and visualizations from various data sources."},

  // -- D3: Global Infrastructure --
  {d:3, t:"recall", q:"What is the purpose of AWS Local Zones?",
   o:["To provide lower-cost storage options","To extend an AWS Region closer to end users for low-latency applications","To manage DNS routing globally","To provide dedicated hardware for compliance"],
   a:1, e:"AWS Local Zones place compute, storage, and database services closer to large population centers, enabling single-digit millisecond latency for end users."},

  {d:3, t:"recall", q:"Which AWS service improves application performance by routing traffic through the AWS global network instead of the public internet?",
   o:["Amazon CloudFront","AWS Global Accelerator","Amazon Route 53","AWS Direct Connect"],
   a:1, e:"AWS Global Accelerator routes traffic through the AWS global network to the optimal endpoint, improving availability and performance for global applications."},

  // -- D3: Developer Tools --
  {d:3, t:"recall", q:"Which AWS service provides a fully managed CI/CD pipeline?",
   o:["AWS CodeBuild","AWS CodeDeploy","AWS CodePipeline","AWS CodeCommit"],
   a:2, e:"AWS CodePipeline is a CI/CD service that automates the build, test, and deploy phases of your release process every time there is a code change."},

  {d:3, t:"recall", q:"Which AWS service provides distributed tracing to debug and analyze microservices applications?",
   o:["Amazon CloudWatch","AWS CloudTrail","AWS X-Ray","AWS Config"],
   a:2, e:"AWS X-Ray helps developers analyze and debug distributed applications by providing end-to-end tracing of requests as they travel through your services."},

  // -- D3: Business Services --
  {d:3, t:"scenario", q:"A company wants to set up a cloud-based contact center to handle customer phone calls. Which AWS service should they use?",
   o:["Amazon SES","Amazon SNS","Amazon Connect","Amazon WorkSpaces"],
   a:2, e:"Amazon Connect is a cloud-based contact center service that makes it easy to set up and manage a customer contact center with voice and chat capabilities."},

  {d:3, t:"scenario", q:"A company needs to provide remote employees with managed virtual desktops. Which AWS service should they use?",
   o:["Amazon AppStream 2.0","Amazon WorkSpaces","Amazon EC2","Amazon Lightsail"],
   a:1, e:"Amazon WorkSpaces is a managed Desktop-as-a-Service (DaaS) solution that provides virtual desktops accessible from any supported device."},

  // -- D3: Infrastructure as Code --
  {d:3, t:"recall", q:"Which AWS service lets you define cloud infrastructure using JSON or YAML templates?",
   o:["AWS Systems Manager","AWS Config","AWS CloudFormation","AWS Elastic Beanstalk"],
   a:2, e:"AWS CloudFormation lets you model and provision AWS resources using templates written in JSON or YAML, enabling infrastructure as code."},

  // -- D3: Multi-select additions --
  {d:3, t:"recall", q:"Which TWO AWS services are AI/ML services that require NO machine learning expertise? (Select TWO)",
   o:["Amazon SageMaker","Amazon Rekognition","Amazon EMR","Amazon Lex","Amazon Redshift"],
   a:[1,3], pick:2, e:"Rekognition (image/video analysis) and Lex (chatbots) are pre-trained AI services that require no ML expertise. SageMaker is for building custom ML models."},

  // -- D4: Additional --
  {d:4, t:"recall", q:"Which AWS service provides automated best practice checks across cost optimization, security, performance, fault tolerance, and service limits?",
   o:["AWS Config","Amazon Inspector","AWS Trusted Advisor","AWS Security Hub"],
   a:2, e:"AWS Trusted Advisor inspects your AWS environment and provides recommendations across five categories: cost optimization, performance, security, fault tolerance, and service limits."},

  {d:4, t:"recall", q:"Where can customers find and purchase third-party software that runs on AWS?",
   o:["AWS Artifact","AWS Marketplace","AWS Partner Network","AWS Service Catalog"],
   a:1, e:"AWS Marketplace is a digital catalog where customers can find, buy, and deploy third-party software and services that run on AWS."},

  {d:4, t:"scenario", q:"A company wants to receive personalized alerts about AWS service disruptions that may affect their resources. Which tool should they use?",
   o:["AWS Trusted Advisor","AWS Health Dashboard","Amazon CloudWatch","AWS Config"],
   a:1, e:"AWS Health Dashboard provides personalized alerts about AWS service health events and scheduled maintenance that may affect your specific resources."},

  {d:4, t:"recall", q:"Which AWS service recommends optimal EC2 instance types based on your actual utilization data?",
   o:["AWS Trusted Advisor","AWS Compute Optimizer","AWS Cost Explorer","AWS Budgets"],
   a:1, e:"AWS Compute Optimizer analyzes your resource utilization and recommends optimal AWS resource configurations to reduce costs and improve performance."},

  {d:4, t:"scenario", q:"A company needs to report abuse of AWS resources being used for phishing attacks. Who should they contact?",
   o:["AWS Support Center","AWS Trust and Safety team","AWS Professional Services","AWS Partner Network"],
   a:1, e:"The AWS Trust and Safety team handles reports of abuse of AWS resources, including spam, phishing, malware hosting, and other prohibited activities."}
];
