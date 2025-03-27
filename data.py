db_info = {
    "tables": "My database contains 4 tables: users, products, orders, orders_content",
    "table_relationships": (
        "Each order (orders) belongs to one user (users), linked by user_id (many-to-one)\n"
        "Each order (orders) contains multiple entries in orders_content (one-to-many)\n"
        "Each orders_content entry links to one product (products) by product_id (many-to-one)\n"
    ),
    "users": (
        "user_id (INTEGER, PRIMARY KEY) - Unique identifier for each user\n"
        "first_name (TEXT) - First name of the user\n"
        "last_name (TEXT) - Last name of the user\n"
        "age (INTEGER, must be non-negative) - Age of the user\n"
        "registration_date (DATE) - The date when the user registered\n"
    ),
    "products": (
        "product_id (INTEGER, PRIMARY KEY) - Unique identifier for each product\n"
        "product_name (TEXT) - Name of the product\n"
        "product_desc (TEXT) - Description of the product\n"
        "price (DECIMAL) - Price of the product\n"
    ),
    "orders": (
        "order_id (INTEGER, PRIMARY KEY) - Unique identifier for each order\n"
        "user_id (INTEGER, FOREIGN KEY references users.user_id) - The ID of the user who placed the order\n"
        "date (DATE) - The date when the order was placed. It covers JUST the year 2025. From 1st of January to 31th of December.\n"
    ),
    "orders_content": (
        "orders_content_id (INTEGER, PRIMARY KEY) - Distinct ID for each product-order relationship\n"
        "order_id (INTEGER, FOREIGN KEY references orders.order_id) - ID of the corresponding order\n"
        "product_id (INTEGER, FOREIGN KEY references products.product_id) - ID of the corresponding product\n"
        "units (INTEGER) - Number of units of each product in the order\n"
    )
}
