package semanticExamples.hardOrderWorkflow

import akka.actor._

final case class OpenOrder(orderId: Int)
final case class AddItem(orderId: Int, quantity: Int)
final case class SubmitOrder(orderId: Int)
final case class ReserveItems(orderId: Int, quantity: Int)
final case class AuditOrder(orderId: Int, quantity: Int)
case object Noop

final class Order(warehouse: ActorRef) extends Actor {
  private var activeOrderId: Int = 0
  private var itemCount: Int = 0
  private var submitted: Boolean = false

  override def receive: Receive = {
    case OpenOrder(orderId) =>
      activeOrderId = orderId
      itemCount = 0
      submitted = false

    case AddItem(orderId, quantity) =>
      if (orderId == activeOrderId) {
        itemCount += quantity
      }

    case SubmitOrder(orderId) =>
      if (orderId == activeOrderId) {
        submitted = true
        warehouse ! ReserveItems(orderId, itemCount)
      }
  }
}

final class Warehouse(audit: ActorRef) extends Actor {
  private var lastOrderId: Int = 0
  private var lastQuantity: Int = 0

  override def receive: Receive = {
    case ReserveItems(orderId, quantity) =>
      lastOrderId = orderId
      lastQuantity = quantity
      audit ! AuditOrder(orderId, quantity)
  }
}

final class Audit extends Actor {
  private var auditedOrderId: Int = 0
  private var auditedQuantity: Int = 0
  private var received: Boolean = false

  override def receive: Receive = {
    case AuditOrder(orderId, quantity) =>
      auditedOrderId = orderId
      auditedQuantity = quantity
      received = true
  }
}

final class Client(order: ActorRef, warehouse: ActorRef, audit: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object HardOrderWorkflow extends App {
  val system = ActorSystem("HardOrderWorkflowSystem")
  val audit = system.actorOf(Props[Audit](), name = "audit")
  val warehouse = system.actorOf(Props(new Warehouse(audit)), name = "warehouse")
  val order = system.actorOf(Props(new Order(warehouse)), name = "order")
  val client = system.actorOf(Props(new Client(order, warehouse, audit)), name = "client")
}
