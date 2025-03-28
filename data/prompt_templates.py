template_prompt = """
This is the user's prompt: '{initial_prompt}'.
This is the database structure: {db_info}

Analyze the prompt and strictly respond with one of these:
- *INSERT* if the prompt contains any of: insert, add, create, new, register, introduce, enter, store, save, append, put, establish, initialize, generate, make, load, populate, enroll, submit, post
- *RETRIEVE* if the prompt contains any of: get, find, show, list, return, select, fetch, query, search, lookup, extract, obtain, view, display, print, read, check, verify, examine, scan
- *ERROR* if not database-related or tables don't exist

Respond with exactly one of: *INSERT* *RETRIEVE* *ERROR* and no other word. The output will mandatory be one of these 3.
"""

template_prompt_1 = """
# PostgreSQL Query Generation Prompt

"I need a PostgreSQL query that fulfills this request: {initial_prompt}

## Database Context
Available tables:
- users (user_id, first_name, last_name, age, registration_date)
- products (product_id, product_name, product_desc, price)
- orders (order_id, user_id, date)
- orders_content (orders_content_id, order_id, product_id, units)

Relationships:
- orders.user_id → users.user_id
- orders_content.order_id → orders.order_id
- orders_content.product_id → products.product_id

## Goal
- Create a valid PostgreSQL query matching the user's request
- Use only the specified tables/columns with proper joins
- Validate all foreign key relationships
- Return ONLY the raw SQL query (no explanations)

## Return Format
A single PostgreSQL query in plain text format

## Warnings
- Reject any tables/columns not in the provided schema
- Ensure proper joins using the documented relationships
- Validate date constraints (orders only cover 2025)
- Check age non-negativity requirements
- Handle decimal precision for price calculations

## Context Dump
User seeks data about: {initial_prompt}
Special considerations: 
- Order dates strictly within 2025
- Age must be non-negative
- Price calculations need proper decimal handling
"""

template_prompt_2 = """
# Query Validation Prompt

"I need to verify if this PostgreSQL query: {answer}
accurately solves: {initial_prompt}

## Database Context
Available tables:
- users (user_id, first_name, last_name, age, registration_date)
- products (product_id, product_name, product_desc, price)
- orders (order_id, user_id, date)
- orders_content (orders_content_id, order_id, product_id, units)

## Goal
- Confirm query matches all user requirements
- Identify schema mismatches or logic errors
- Validate all joins and constraints
- Check for proper date filtering (2025 only)

## Return Format
First line: 'yes' or 'no' 
Second line: Error explanation (if 'no') + fix suggestion

## Warnings
- Flag incorrect table/column references
- Catch invalid joins missing relationship paths
- Verify date constraints (orders.date must be in 2025)
- Check age non-negativity enforcement
- Validate decimal handling for price calculations

## Context Dump
Query purpose: {initial_prompt}
Critical constraints:
- All order dates must be in 2025
- User ages cannot be negative
- Price calculations require precision
"""

template_prompt_3 = """
User's prompt: {initial_prompt}
The query was executed correctly. It was a {type} query.
Provide a one line conclusion about the prompt and say it was a successful operation.
"""

template_prompt_4 = """
Database: {db_info}
Prompt: "{initial_prompt}"

Instructions:
1. Identify which table the command is targeting. The possible tables are:
   - users
   - products
   - orders
   - orders_content

2. For the identified table, verify that the following required columns are provided:
   - For **users**: first_name, last_name, age, registration_date
   - For **products**: product_name, product_desc, price
   - For **orders**: user_id, date
   - For **orders_content**: order_id, product_id, units

3. Ignore any SERIAL primary key fields.

4. Produce EXACTLY one output:
   - If one or more required columns are missing, return their names as a comma-separated list (e.g., "last_name, age, registration_date").
   - If all required columns are present, return the exact string "all matched".

Examples:
- "register user John Smith 30 2023-05-15" → "all matched"
- "add product 'Laptop' 'Gaming laptop'" → "price"
- "create order for user 5" → "date"
- "add order item 101 205 3" → "all matched"   *(interpreted as orders_content)*
- "insert user named Alice" → "last_name, age, registration_date"
- "add user Bob Johnson" → "age, registration_date"
- "new product 'Monitor' 299.99" → "product_desc"
- "log order user7 2024-02-20" → "all matched"
- "record purchase 102 304" → "units"   *(interpreted as orders_content)*
- "enter user 'Charlie' 'Brown' 28" → "registration_date"

Note:
- For instance, if the command is "insert a user Todor Ioan, aged 20, registered on 01 01 2001", the system must ensure that all required fields for the users table are provided. If any are missing (for example, if it only detects first_name but not last_name, age, and registration_date), the output should list the missing fields (e.g., "last_name, age, registration_date").
- The keyword "*INSERT*" indicates that the command is for an insertion.

Output exactly one of:
- A comma-separated list of missing columns (if any are absent)
- The string "all matched" (if every required column is included)
"""

template_prompt_5 = """
# PostgreSQL INSERT Query Generation Prompt
I need a PostgreSQL INSERT query that fulfills this request: {initial_prompt}

## Database Context
Database structure is available here: {db_info}.

## Goal
- Construct a valid PostgreSQL `INSERT` query that resolves the user's request
- Use only the specified tables/columns while maintaining foreign key integrity
- Ensure all required fields are included for a successful insertion
- Return ONLY the raw SQL query (no explanations)

## Return Format
A single PostgreSQL `INSERT` query in plain text format

## Warnings
- Reject any tables/columns not listed in the schema
- Ensure all required fields are provided
- Validate date constraints (orders only cover 2025)
- Ensure proper handling of numeric values (e.g., age non-negative, price as decimal)
- Maintain relational integrity when inserting related records

## Context Dump
User's request: {initial_prompt}
Database Structure: {db_info}
"""