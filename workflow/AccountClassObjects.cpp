#include "splashkit.h"
#include "utilities.h"

class account
{
    // private members here...
    int balance;    // balance of account in cents

    public:
        // public members here...
        string name;

        account(string _name, int _balance) {
            // Initialise the account
            // We've added _ to the front of parameters, to differentiate them from the class fields
            name = _name;
            balance = _balance;
        }
        account() {
            //  A default constructor lets you initialise the value when no parameters are passed
            name = "Account Holder Unknown";
            balance = 0;
        }

        // This should output the account in any format you desire, as long as it shows the account name and the balance.
        void print() {
            write_line(name + ": $" + to_string(balance / 100.0));
        }

        void withdraw() {
            int amount = read_unsigned_integer("Please input the amount of fund to  withdown: ");
            balance -= amount;
        }
        void deposit() {
            int amount = read_unsigned_integer("Please input the amount of fund to  deposit: ");
            balance += amount;
        }
};

int main() {
    // Create 5 accounts objects on the stack
    account a1("Atabak", 100);
    account a2("Sheena", 734231);
    account a3("Azadeh", 90210);
    account a4("Jo", -1000);
    account a5;

    // Print the accounts
    a1.print();
    a2.print();
    a3.print();
    a4.print();
    a5.print();
    
    a1.deposit();
    a2.withdraw();
    a1.print();
    a2.print();
    
    return 0;
}