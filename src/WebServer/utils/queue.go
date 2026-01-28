package utils
import (
	"container/list"
)

// 这里我们使用双向链表实现队列
type ListQueue struct {
	list *list.List
}

func NewListQueue() *ListQueue {
	return &ListQueue{ //创建指针
		list: list.New(), // 创建了一个新的空双向链表
	}
}

func (q *ListQueue) Enqueue(value interface{}) { //添加到末尾
	q.list.PushBack(value)
}

func (q *ListQueue) Dequeue() interface{} { //出队
	if q.list.Len() == 0 {
		return nil
	}
	front := q.list.Front() //返回的是指向链表第一个元素的指针
	q.list.Remove(front)
	return front.Value
}

func (q *ListQueue) Front() interface{} { //只获得队首的元素
	if q.list.Len() == 0 {
		return nil
	}
	return q.list.Front().Value
}

func (q *ListQueue) IsEmpty() bool {
	return q.list.Len() == 0
}

func (q *ListQueue) Size() int {
	return q.list.Len()
}

// 不能直接用迭代器，因为这个没有迭代器的接口，只能复制赋值来获得值
func (q *ListQueue) GetAll() []interface{} {
    // 创建一个切片来存储所有元素
    elements := make([]interface{}, 0, q.list.Len())
    
    // 从链表头部开始遍历
    for e := q.list.Front(); e != nil; e = e.Next() {
        elements = append(elements, e.Value)
    }
    
    return elements  
}
