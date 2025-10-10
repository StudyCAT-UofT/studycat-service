import asyncio
from client import db


async def test_db_connection():
    """Test the database connection by fetching users."""
    try:
        # Connect to the database
        await db.connect()
        print("✓ Successfully connected to the database")
        
        # Fetch all users
        users = await db.user.find_many()
        print(f"✓ Found {len(users)} users in the database")
        
        if users:
            print("\nUsers:")
            for user in users:
                print(f"  - {user.username} (ID: {user.id}, Created: {user.createdAt})")
        else:
            print("\nNo users found in the database yet.")
        
        # Try fetching courses as well
        courses = await db.course.find_many()
        print(f"\n✓ Found {len(courses)} courses in the database")
        
        if courses:
            print("\nCourses:")
            for course in courses:
                print(f"  - {course.code}: {course.title} (ID: {course.id})")
        else:
            print("\nNo courses found in the database yet.")
        
        print("\n✓ Database test completed successfully!")
        
    except Exception as e:
        print(f"✗ Error during database test: {e}")
        raise
    finally:
        # Disconnect from the database
        await db.disconnect()
        print("✓ Disconnected from the database")


if __name__ == "__main__":
    asyncio.run(test_db_connection())

