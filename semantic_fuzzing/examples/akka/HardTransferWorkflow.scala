package semanticExamples.hardTransferWorkflow

import akka.actor._

final case class BeginTransfer(transferId: Int, amount: Int)
final case class DebitRequest(transferId: Int, amount: Int)
final case class Credit(amount: Int)
final case class TransferRecorded(transferId: Int, approved: Boolean)
case object Noop

final class Coordinator(source: ActorRef) extends Actor {
  private var activeTransferId: Int = 0
  private var requestedAmount: Int = 0

  override def receive: Receive = {
    case BeginTransfer(transferId, amount) =>
      activeTransferId = transferId
      requestedAmount = amount
      source ! DebitRequest(transferId, amount)
  }
}

final class SourceAccount(target: ActorRef, audit: ActorRef) extends Actor {
  private var balance: Int = 100
  private var lastDebitSucceeded: Boolean = false

  override def receive: Receive = {
    case DebitRequest(transferId, amount) =>
      if (balance >= amount) {
        balance -= amount
        lastDebitSucceeded = true
        target ! Credit(amount)
        audit ! TransferRecorded(transferId, true)
      } else {
        lastDebitSucceeded = false
        audit ! TransferRecorded(transferId, false)
      }
  }
}

final class TargetAccount extends Actor {
  private var balance: Int = 0
  private var credited: Boolean = false

  override def receive: Receive = {
    case Credit(amount) =>
      balance += amount
      credited = true
  }
}

final class Audit extends Actor {
  private var lastTransferId: Int = 0
  private var lastApproved: Boolean = false

  override def receive: Receive = {
    case TransferRecorded(transferId, approved) =>
      lastTransferId = transferId
      lastApproved = approved
  }
}

final class Client(coordinator: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object HardTransferWorkflow extends App {
  val system = ActorSystem("HardTransferWorkflowSystem")
  val target = system.actorOf(Props[TargetAccount](), name = "target")
  val audit = system.actorOf(Props[Audit](), name = "audit")
  val source = system.actorOf(
    Props(new SourceAccount(target, audit)),
    name = "source"
  )
  val coordinator = system.actorOf(
    Props(new Coordinator(source)),
    name = "coordinator"
  )
  val client = system.actorOf(Props(new Client(coordinator)), name = "client")
}
