---
title: "[BOJ] INU 송년 코드페스티벌 2019 Open Contest"
categories: [PS]
tags: [BOJ, 백준, INU, 인천대, 18228, 18229, 18230, 18231, 18232, 18234, 18235]
---

# [18228번: 펭귄추락대책위원회](https://www.acmicpc.net/problem/18228)
## 풀이
 -1을 기준으로 좌측과 우측의 최소값의 합을 구한다.
 <br>

## 코드

``` java
import java.io.*;
import java.util.*;

public class Main {

    static FastIO io = new FastIO();

    public static void main(String... args) throws IOException {
        int N = io.nextInt(), A, res = 0;
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        for (int i = 0; i < N; i++) {
            if ((A = io.nextInt()) == -1) {
                res += pq.poll();
                pq.clear();
                continue;
            }

            pq.add(A);
        }

        io.write(res += pq.poll());
    }
}

class FastIO { ... } // 생략
```
<br>
<br>

# [18229번: 내가 살게, 아냐 내가 살게](https://www.acmicpc.net/problem/18229)

## 풀이
 문제 조건대로 정직하게 구현한다.
 <br>

## 코드

``` java
import java.io.*;
import java.util.*;

public class Main {

    static FastIO io = new FastIO();

    public static void main(String... args) throws IOException {
        int N = io.nextInt(), M = io.nextInt(), K = io.nextInt();
        int[][] arr = new int[N + 1][M + 1];
        int[] arr2 = new int[N + 1];
        Arrays.fill(arr2, 0);
        StringBuilder res = new StringBuilder();

        for (int i = 1; i < N + 1; i++) {
            for (int j = 1; j < M + 1; j++) {
                arr[i][j] = io.nextInt();
            }
        }

        for (int i = 1; i < M + 1; i++) {
            for (int j = 1; j < N + 1; j++) {
                arr2[j] += arr[j][i];
                if (arr2[j] >= K) {
                    res.append(j).append(' ').append(i);
                    io.write(res);
                    return;
                }
            }
        }
    }

}

class FastIO { ... } // 생략
```

<br>
<br>

# [18230번: 2xN 예쁜 타일링](https://www.acmicpc.net/problem/18230)
## 풀이
 A개의 값을 가지는 a배열과 B개의 값을 가지는 b배열을 내림차순으로 정렬한다.<br>
정렬할 수 있는 모든 조합을 하면서 최댓값을 찾는다.<br>

```
ex)
X = 2 * 1 + 1 * (X - 2 * 1)
  = 2 * 2 + 1 * (X - 2 * 2)
  = ...
```
<br>

## 코드
``` cpp
#include <iostream>
#include <vector>
#include <algorithm>
#include <functional>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    int N, A, B, k, ans = -1, sum;
    cin >> N >> A >> B;
    vector<int> a(A + 1, 0), b(B + 1, 0);
    for (int i = 1; i < A + 1; i++)
    {
        cin >> a[i];
    }
    for (int i = 1; i < B + 1; i++)
    {
        cin >> b[i];
    }
    sort(a.begin() + 1, a.end(), greater<int>());
    sort(b.begin() + 1, b.end(), greater<int>());
    for (int i = 0; i < N / 2 + 1; i++)
    {
        k = N - 2 * i;
        if (k > A || i > B)
            continue;
        sum = 0;
        for (int j = 1; j < k + 1; j++)
        {
            sum += a[j];
        }
        for (int j = 1; j < i + 1; j++)
        {
            sum += b[j];
        }
        ans = max(ans, sum);
    }
    return !(cout << ans);
}
```

<br>
<br>

# [18231번: 파괴된 도시](https://www.acmicpc.net/problem/18231)
## 풀이
 1. 주어진 입력으로 인접리스트를 구성한다.
 2. 파괴된 도시 중 첫 번째 도시를 기준으로 disjoint set을 구성한다.
 3. 파괴된 도시의 인접 도시들을 순회한다.
   - 인접 도시가 파괴된 도시가 아닐경우 반복문을 탈출한다.
   - 인접 도시가 모두 파괴된 도시일 경우 정답 리스트(ans)에 넣어준다.
 4. 정답 리스트의 도시들과 그 도시들의 인접한 도시들을 Set에 넣어준다.
   - Set의 크기가 K보다 작으면 -1을 출력한다.
   - 그 외의 경우에는 정답 리스트를 출력한다.
<br>

## 애로사항
 정답 리스트의 크기가 비어있지 않더라도 -1을 출력하는 경우가 있을 수 있다.
```
ex)
7 7
1 2
1 4
2 3
2 5
4 5
4 6
5 7

output: -1
```

<br>
## 코드

``` java
import java.io.*;
import java.util.*;

public class Main {

    static FastIO io = new FastIO();
    static List<List<Integer>> adj;
    static List<Integer> destroyed, ans;
    static int[] parent;
    static int N, M, U, V, K, P, dtr;

    public static void main(String... args) throws IOException {
        N = io.nextInt();
        M = io.nextInt();
        adj = new ArrayList<>(N + 1);
        for (int i = 0; i < N + 1; i++) {
            adj.add(new ArrayList<>());
        }
        parent = new int[N + 1];
        Arrays.setAll(parent, i -> i);
        destroyed = new ArrayList<>();
        ans = new ArrayList<>();
        StringBuilder res = new StringBuilder();
        for (int i = 0; i < M; i++) {
            U = io.nextInt();
            V = io.nextInt();
            adj.get(U).add(V);
            adj.get(V).add(U);
        }
        K = io.nextInt();
        dtr = io.nextInt();
        destroyed.add(dtr);
        for (int i = 0; i < K - 1; i++) {
            P = io.nextInt();
            union(dtr, P);
            destroyed.add(P);
        }

        for (int i = 1; i < N + 1; i++) {
            if (find(i) != dtr)
                continue;

            boolean flag = true;

            for (int j : adj.get(i)) {
                if (find(j) != dtr) {
                    flag = false;
                    break;
                }
            }

            if (flag)
                ans.add(i);
        }

        if (ans.isEmpty())
            res.append(-1);

        else {
            Set<Integer> hs = new HashSet<>();

            for (Integer i : ans) {
                hs.add(i);
                boolean flag = true;

                for (Integer j : adj.get(i)) {
                    if (find(j) != dtr) {
                        flag = false;
                        break;
                    }
                }

                if (flag)
                    for (Integer j : adj.get(i)) {
                        hs.add(j);
                    }
            }

            if (hs.size() < K) {
                io.write(-1);
                return;
            }
            
            res.append(ans.size()).append('\n');
            for (int i : ans) {
                res.append(i).append(' ');
            }
        }

        io.write(res);
    }

    private static int find(int x) {
        if (x == parent[x])
            return x;
        return parent[x] = find(parent[x]);
    }

    private static void union(int x, int y) {
        x = find(x);
        y = find(y);

        if (x != y)
            parent[y] = x;
    }

}

class FastIO { ... }    // 생략
```

<br>
<br>

# [18231번: 파괴된 도시](https://www.acmicpc.net/problem/18231)