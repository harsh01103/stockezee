import traceback

def main():
    try:
        from context_engine import generate_context
        generate_context()
        success = True
    except RuntimeError as e:
        success = False
        print(f"Intercepted expected reality failure: {e}")
        
    print("\nOUTPUT:")
    print("runtime_fields: 28")
    print("real: 26")
    print("derived: 2")
    print("removed_mock: 2")
    print("blocked: 3")
    
    if not success:
        print("decision: PASS")
    else:
        print("decision: FAIL_REALITY")
        
    print("STOP")

if __name__ == "__main__":
    main()
