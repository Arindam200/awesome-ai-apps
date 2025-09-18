```markdown
### Problem Statement

Given an array of integers `nums` and an integer `target`, find all unique quadruplets `[nums[i], nums[j], nums[left], nums[right]]` such that `nums[i] + nums[j] + nums[left] + nums[right] == target`. The solution should not contain duplicate quadruplets.

### Approach Summary

The algorithm sorts the input array `nums` and then iterates through all possible pairs of the first two elements of the quadruplet. For each pair, it uses a two-pointer approach to find the remaining two elements such that the sum of the quadruplet equals the target. Duplicate quadruplets are avoided by skipping duplicate elements for the first two numbers and also skipping duplicate elements when adjusting the left and right pointers.

### Detailed Approach

1.  **Sort the array:** Sort the input array `nums` in ascending order. This allows for the use of the two-pointer technique and helps in skipping duplicate quadruplets.
2.  **Iterate through the first two numbers:** Use nested loops to iterate through all possible pairs `(i, j)` of the first two elements of the quadruplet. The outer loop iterates from `i = 0` to `n - 3`, and the inner loop iterates from `j = i + 1` to `n - 2`.
3.  **Skip duplicate elements:** To avoid duplicate quadruplets, skip duplicate elements for the first and second numbers. If `i > 0` and `nums[i] == nums[i - 1]`, continue to the next iteration of the outer loop. Similarly, if `j > i + 1` and `nums[j] == nums[j - 1]`, continue to the next iteration of the inner loop.
4.  **Two-pointer approach:** For each pair `(i, j)`, use a two-pointer approach to find the remaining two elements `(left, right)` such that `nums[i] + nums[j] + nums[left] + nums[right] == target`. Initialize `left = j + 1` and `right = n - 1`.
5.  **Adjust pointers:** While `left < right`, calculate the current sum `current_sum = nums[i] + nums[j] + nums[left] + nums[right]`. If `current_sum == target`, add the quadruplet `[nums[i], nums[j], nums[left], nums[right]]` to the result. Then, skip duplicate elements for the third and fourth numbers by incrementing `left` while `left < right` and `nums[left] == nums[left + 1]`, and decrementing `right` while `left < right` and `nums[right] == nums[right - 1]`. Finally, increment `left` and decrement `right` to move to the next pair of elements.
    *   If `current_sum < target`, increment `left` to increase the sum.
    *   If `current_sum > target`, decrement `right` to decrease the sum.
6.  **Return the result:** After iterating through all possible pairs `(i, j)`, return the list of unique quadruplets.

### Time Complexity

O(n^3), where n is the length of the input array `nums`. The algorithm has three nested loops: the outer loop iterates n-3 times, the inner loop iterates n-2 times, and the two-pointer approach takes O(n) time in the worst case. The sorting operation takes O(n log n) time, but it is dominated by the O(n^3) time complexity of the nested loops.

### Space Complexity

O(1) or O(n). In the best case, the algorithm uses O(1) extra space if the sorting algorithm used is in-place. However, if the sorting algorithm uses O(n) space (e.g., merge sort), then the space complexity of the algorithm is O(n).  The space required to store the result is not considered in the space complexity analysis.

### Code Walkthrough

1.  `n = len(nums)`: Get the length of the input array `nums`.
2.  `result = []`: Initialize an empty list `result` to store the quadruplets.
3.  `nums.sort()`: Sort the input array `nums` in ascending order.
4.  `for i in range(n - 3)`: Iterate through the first element of the quadruplet.
5.  `if i > 0 and nums[i] == nums[i - 1]: continue`: Skip duplicate elements for the first number.
6.  `for j in range(i + 1, n - 2)`: Iterate through the second element of the quadruplet.
7.  `if j > i + 1 and nums[j] == nums[j - 1]: continue`: Skip duplicate elements for the second number.
8.  `left = j + 1`: Initialize the left pointer to `j + 1`.
9.  `right = n - 1`: Initialize the right pointer to `n - 1`.
10. `while left < right`: While the left pointer is less than the right pointer.
11. `current_sum = nums[i] + nums[j] + nums[left] + nums[right]`: Calculate the current sum of the four elements.
12. `if current_sum == target`: If the current sum is equal to the target.
13. `result.append([nums[i], nums[j], nums[left], nums[right]])`: Add the quadruplet to the result.
14. `while left < right and nums[left] == nums[left + 1]: left += 1`: Skip duplicate elements for the third number.
15. `while left < right and nums[right] == nums[right - 1]: right -= 1`: Skip duplicate elements for the fourth number.
16. `left += 1`: Move the left pointer to the right.
17. `right -= 1`: Move the right pointer to the left.
18. `elif current_sum < target`: If the current sum is less than the target, move the left pointer to the right.
19. `else`: If the current sum is greater than the target, move the right pointer to the left.
20. `return result`: Return the list of unique quadruplets.

### Edge Cases

1.  **Empty array:** If the input array is empty, the function should return an empty list.
2.  **Array with fewer than four elements:** If the input array has fewer than four elements, the function should return an empty list.
3.  **Duplicate elements:** The function should handle duplicate elements correctly and avoid returning duplicate quadruplets.
4.  **Target not found:** If no quadruplets sum up to the target, the function should return an empty list.
5.  **Large input array:** The function should be efficient enough to handle large input arrays.

### Key Concepts

1.  **Sorting:** Sorting the input array allows for the use of the two-pointer technique and helps in skipping duplicate quadruplets.
2.  **Two-pointer technique:** The two-pointer technique is used to efficiently find the remaining two elements of the quadruplet such that the sum of the quadruplet equals the target.
3.  **Skipping duplicate elements:** Skipping duplicate elements is crucial to avoid returning duplicate quadruplets.

### Example Input

`nums = [1, 0, -1, 0, -2, 2], target = 0`. This example is good because it contains both positive and negative numbers, duplicates, and multiple quadruplets that sum to the target.

### Step-by-Step Trace

Let's trace the execution with the input `nums = [1, 0, -1, 0, -2, 2]` and `target = 0`:\
4.  `n = 6`
5.  `result = []`
6.  `nums.sort()`: `nums` becomes `[-2, -1, 0, 0, 1, 2]`
7.  `i = 0`: `nums[i] = -2`
8.  `j = 1`: `nums[j] = -1`
9.  `left = 2`: `nums[left] = 0`
10. `right = 5`: `nums[right] = 2`
11. `current_sum = -2 + -1 + 0 + 2 = -1`
12. `current_sum < target`: `left = 3`, `nums[left] = 0`
13. `current_sum = -2 + -1 + 0 + 2 = -1`
14. `current_sum < target`: `left = 4`, `nums[left] = 1`
15. `current_sum = -2 + -1 + 1 + 2 = 0`
16. `result.append([-2, -1, 1, 2])`
17. `left = 5`, `right = 4`: `left > right`, break while loop
18. `j = 2`: `nums[j] = 0`
19. `left = 3`, `nums[left] = 0`
20. `right = 5`, `nums[right] = 2`
21. `current_sum = -2 + 0 + 0 + 2 = 0`
22. `result.append([-2, 0, 0, 2])`
23. `left = 4`, `right = 1`: `left > right`, break while loop.
24. `i = 1`: `nums[i] = -1`
25. `j = 2`: `nums[j] = 0`
26. `left = 3`: `nums[left] = 0`
27. `right = 5`: `nums[right] = 2`
28. `current_sum = -1 + 0 + 0 + 2 = 1`
29. `current_sum > target`: `right = 4`, `nums[right] = 1`
30. `current_sum = -1 + 0 + 0 + 1 = 0`
31. `result.append([-1, 0, 0, 1])`
32. ... the algorithm continues, skipping duplicate quadruplets
33. Finally, the algorithm returns `result = [[-2, -1, 1, 2], [-2, 0, 0, 2], [-1, 0, 0, 1]]`

### Visual Representation

```
Input: [1, 0, -1, 0, -2, 2], target = 0

Sorted: [-2, -1, 0, 0, 1, 2]

Outer loop (i):
  -2: Inner loop (j):
    -1: left=0, right=2 -> [-2, -1, 0, 2] = -1 < 0, left++
          left=1, right=2 -> [-2, -1, 1, 2] = 0 == 0, result.add([-2, -1, 1, 2])
    0(1): left=2, right=2 -> [-2, 0, 0, 2] = 0 == 0, result.add([-2, 0, 0, 2])
-1: Inner loop (j):
    0: left=1, right=2 -> [-1, 0, 0, 1] = 0 == 0, result.add([-1, 0, 0, 1])
Output: [[-2, -1, 1, 2], [-2, 0, 0, 2], [-1, 0, 0, 1]]

Visualization of the Two-Pointer Approach:

[-2, -1, 0, 0, 1, 2]
 i   j    L        R

```

### Intermediate Outputs

1.  `nums.sort()`: `nums` becomes `[-2, -1, 0, 0, 1, 2]`
2.  Quadruplets found: `[-2, -1, 1, 2]`, `[-2, 0, 0, 2]`, `[-1, 0, 0, 1]`

### Final Result

The function returns `[[-2, -1, 1, 2], [-2, 0, 0, 2], [-1, 0, 0, 1]]`.  The sum of each quadruplet is equal to the target 0, and there are no duplicate quadruplets in the result.
```