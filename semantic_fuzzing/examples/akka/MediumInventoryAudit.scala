package semanticExamples.mediumInventoryAudit

import akka.actor._

final case class AddStock(quantity: Int)
final case class Reserve(quantity: Int)
final case class ReservationRecorded(quantity: Int, accepted: Boolean)
case object Noop

final class Inventory(audit: ActorRef) extends Actor {
  private var available: Int = 0
  private var reserved: Int = 0

  override def receive: Receive = {
    case AddStock(quantity) =>
      available += quantity

    case Reserve(quantity) =>
      if (available >= quantity) {
        available -= quantity
        reserved += quantity
        audit ! ReservationRecorded(quantity, true)
      } else {
        audit ! ReservationRecorded(quantity, false)
      }
  }
}

final class Audit extends Actor {
  private var lastQuantity: Int = 0
  private var lastAccepted: Boolean = false

  override def receive: Receive = {
    case ReservationRecorded(quantity, accepted) =>
      lastQuantity = quantity
      lastAccepted = accepted
  }
}

final class Client(inventory: ActorRef, audit: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object MediumInventoryAudit extends App {
  val system = ActorSystem("MediumInventoryAuditSystem")
  val audit = system.actorOf(Props[Audit](), name = "audit")
  val inventory = system.actorOf(Props(new Inventory(audit)), name = "inventory")
  val client = system.actorOf(Props(new Client(inventory, audit)), name = "client")
}
