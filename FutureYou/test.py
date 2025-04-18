from datetime import datetime, timezone, timedelta
    

    
def main():
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1)
    updated_str = since.strftime("DateTime(%Y, %m, %d)")
    print(f"Updated Date String: {updated_str}")
    
if __name__ == "__main__":
    main()