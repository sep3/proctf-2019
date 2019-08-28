using System;
using System.Linq;
using System.Threading.Tasks;
using Deer.Helpers;
using EasyNetQ;
using EasyNetQ.Management.Client;
using EasyNetQ.Management.Client.Model;
using Microsoft.Extensions.Logging;
using ExchangeType = RabbitMQ.Client.ExchangeType;

namespace Deer.Repositories
{
    public class UserUnitOfWork : IUserUnitOfWork
    {
        private readonly IManagementClient _managementClient;
        private readonly IUserRepository _userRepository;
        private readonly IBus _bus;
        private readonly IOpenDistroElasticsearchClient _elasticsearchClient;
        private readonly ILogConsumerService _logConsumerService;
        private readonly ILogger<UserUnitOfWork> _logger;

        public UserUnitOfWork(IManagementClient managementClient, IUserRepository userRepository, IBus bus, IOpenDistroElasticsearchClient elasticsearchClient, ILogConsumerService logConsumerService, ILogger<UserUnitOfWork> logger)
        {
            _managementClient = managementClient;
            _userRepository = userRepository;
            _bus = bus;
            _elasticsearchClient = elasticsearchClient;
            _logConsumerService = logConsumerService;
            _logger = logger;
        }

        public async Task<bool> CreateUserAsync(string username, string password)
        {
            var vhost = await _managementClient.GetVhostAsync("/");

            if ((await _managementClient.GetUsersAsync()).Any(u => string.Equals(u.Name, username, StringComparison.InvariantCultureIgnoreCase)))
            {
                _logger.LogInformation($"User '{username}' already exists");
                return false;
            }
            
            var userInfo = new UserInfo(username, password);
            var rabbitUser = await _managementClient.CreateUserAsync(userInfo);
            _logger.LogInformation($"RabbitMQ user '{username}' created");

            var logExchangeName = $"logs.{username}";
            var exchangeInfo = new ExchangeInfo(logExchangeName, ExchangeType.Fanout);
            await _managementClient.CreateExchangeAsync(exchangeInfo, vhost);
            _logger.LogInformation($"RabbitMQ exchange for user '{username}' created");
            
            var logQueueName = (await _bus.Advanced.QueueDeclareAsync("")).Name;

            var logExchange = await _managementClient.GetExchangeAsync(logExchangeName, vhost);
            var logQueue = await _managementClient.GetQueueAsync(logQueueName, vhost);
            await _managementClient.CreateBindingAsync(logExchange, logQueue, new BindingInfo(""));
            
            var permissionInfo = new PermissionInfo(rabbitUser, vhost)
                .DenyAllConfigure()
                .SetRead("^amq\\.")
                .SetWrite("^logs\\.");
            await _managementClient.CreatePermissionAsync(permissionInfo);
            _logger.LogInformation($"RabbitMQ permissions for user '{username}' set");

            var errorExchange = await _managementClient.GetExchangeAsync("errors", vhost);
            
            var errorQueueName = (await _bus.Advanced.QueueDeclareAsync("")).Name;
            _logger.LogInformation($"RabbitMQ errors queue for user '{username}' created");
            
            var errorQueue = await _managementClient.GetQueueAsync(errorQueueName, vhost);
            await _managementClient.CreateBindingAsync(errorExchange, errorQueue, new BindingInfo(username));
            _logger.LogInformation($"RabbitMQ error queue for user '{username}' bound to error exchange");

            await _elasticsearchClient.CreateUserAsync(username, password);
            _logger.LogInformation($"ElasticSearch user '{username}' created");
            
            await _elasticsearchClient.CreateIndexAsync(username);
            _logger.LogInformation($"ElasticSearch index for '{username}' created");
            
            var salt = CryptoUtils.GenerateSalt();
            var passwordHash = CryptoUtils.ComputeHash(salt, password);
            
            var user = new Deer.Models.User
            {
                Username = username,
                Salt = salt,
                PasswordHash = passwordHash,
                LogIndexName = username,
                LogExchangeName = logExchangeName,
                LogQueueName = logQueueName,
                ErrorQueueName = errorQueueName
            };
            await _userRepository.CreateAsync(user);
            _logger.LogInformation($"UserInfo for user '{username}' saved to MongoDB");

            await _logConsumerService.AddConsumerForUserAsync(username);
            _logger.LogInformation($"Added log consumer for user '{username}'");
            
            return true;
        }
    }
}