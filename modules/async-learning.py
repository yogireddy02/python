import asyncio

async def function1():
    print("Function 1 invoked")
    await asyncio.sleep(5)
    print("Function 1 completed")
    return 1

async def function2():
    print("Function 2 invoked")
    await asyncio.sleep(1)
    print("Function 2 completed")
    return 2

async def dependent_function(value):
    print(f"Dependent function received: {value}")
    await asyncio.sleep(3)
    result = value * 10
    print(f"Dependent function completed: {result}")
    return result

async def main():
    # Start both concurrently
    task1 = asyncio.create_task(function1())
    task2 = asyncio.create_task(function2())

    # Wait for function2
    result2 = await task2 # 1 sec elapsed still 4 more seconds to finish task 1

    # Execute dependent function using function2 result
    dependent_result = await dependent_function(result2) # called the function with task2 results # 2 scond

    print(f"Dependent result: {dependent_result}")

    # Finally wait for function1
    result1 = await task1


    print(f"Function1 result: {result1}")

asyncio.run(main())