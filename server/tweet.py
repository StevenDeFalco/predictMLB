from datetime import datetime
import sys 

if len(sys.argv) > 1:
    tweet = sys.argv[1]
print(f"\n{datetime.now().strftime('%D - %T')}... "
      f"Tweeting!\n{tweet}\n")

# tweet...
